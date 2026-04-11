import { useCallback } from "react";
import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";
import { createLogger } from "@/lib/logger";
import type { PageData } from "../components/PDF/types";
import { isDbAvailable } from "../db/index";

const log = createLogger("useLayoutPolling");

interface CachedPaperBase {
	id: string;
	file_hash: string;
	title: string;
	last_accessed: number;
	layout_json?: string;
}

interface UseLayoutPollingDeps {
	token: string | null;
	sessionId: string | undefined;
	getCachedPaper: (id: string) => Promise<CachedPaperBase | null | undefined>;
	savePaperToCache: (paper: CachedPaperBase) => Promise<void> | void;
	setPages: React.Dispatch<React.SetStateAction<PageData[]>>;
}

/**
 * レイアウト解析ジョブのキューイング・SSEポーリング・ページへの適用を管理するカスタムフック。
 * PDFViewer から applyLayoutFigures / triggerLazyLayoutAnalysis を切り出したもの。
 */
export function useLayoutPolling({
	token,
	sessionId,
	getCachedPaper,
	savePaperToCache,
	setPages,
}: UseLayoutPollingDeps) {
	/**
	 * バックエンドから返された figures 配列を pages state に適用し、
	 * IndexedDB キャッシュを更新する。
	 */
	const applyLayoutFigures = useCallback(
		(figures: any[], paperId: string, fileHash: string | null) => {
			if (!Array.isArray(figures) || figures.length === 0) return;

			setPages((prevPages) => {
				const nextPages = prevPages.map((page) => {
					const pageFigures = figures.filter(
						(f: any) => f.page_num === page.page_num,
					);
					if (pageFigures.length === 0) return page;

					const processedFigures = pageFigures.map((f: any) => ({
						...f,
						image_url:
							f.image_url &&
							!f.image_url.startsWith("http") &&
							!f.image_url.startsWith("blob:")
								? `${API_URL}${f.image_url}`
								: f.image_url,
					}));

					const existingUrls = new Set(
						(page.figures || []).map((ef) => ef.image_url),
					);
					const newUniqueFigures = processedFigures.filter(
						(nf: any) => !existingUrls.has(nf.image_url),
					);

					if (newUniqueFigures.length === 0) return page;

					return {
						...page,
						figures: [...(page.figures || []), ...newUniqueFigures],
					};
				});

				// IndexedDB キャッシュに永続化（Transient セッション対応）
				if (paperId && isDbAvailable()) {
					const layoutJson = JSON.stringify(
						nextPages.map((p) => ({
							width: p.width,
							height: p.height,
							words: p.words,
							figures: p.figures,
							links: p.links,
						})),
					);

					getCachedPaper(paperId).then((cached) => {
						savePaperToCache({
							...(cached || {
								id: paperId,
								file_hash: fileHash || "",
								title: "Untitled",
								last_accessed: Date.now(),
							}),
							layout_json: layoutJson,
							last_accessed: Date.now(),
						});
					});
				}

				return nextPages;
			});
		},
		[setPages, getCachedPaper, savePaperToCache],
	);

	/** レイアウトジョブの SSE ストリームをポーリングし、完了まで待機する。 */
	const pollLayoutJob = useCallback(
		(
			jobId: string,
			paperId: string,
			fileHash: string | null,
			streamUrl: string,
		): Promise<void> => {
			return new Promise((resolve) => {
				const fullStreamUrl = streamUrl.startsWith("http")
					? streamUrl
					: `${API_URL}${streamUrl}`;
				const es = new EventSource(fullStreamUrl);

				const timeout = setTimeout(() => {
					log.error("poll_layout_job", "Job timed out", { job_id: jobId });
					es.close();
					resolve();
				}, 130_000);

				es.onmessage = (event) => {
					try {
						const data = JSON.parse(event.data);

						if (data.status === "partial") {
							applyLayoutFigures(data.figures, paperId, fileHash);
						} else if (data.status === "completed") {
							log.info("poll_layout_job", "Job completed", {
								job_id: jobId,
								figures: data.figures_detected,
							});
							applyLayoutFigures(data.figures, paperId, fileHash);
							clearTimeout(timeout);
							es.close();
							resolve();
						} else if (data.status === "failed") {
							log.error("poll_layout_job", "Job failed", {
								job_id: jobId,
								error: data.error,
							});
							clearTimeout(timeout);
							es.close();
							resolve();
						} else if (
							data.status === "not_found" ||
							data.status === "timeout"
						) {
							log.warn("poll_layout_job", "Job ended unexpectedly", {
								job_id: jobId,
								status: data.status,
							});
							clearTimeout(timeout);
							es.close();
							resolve();
						}
						// queued / processing → 次の SSE メッセージを待つ
					} catch {
						// ignore parse errors
					}
				};

				es.onerror = () => {
					log.warn("poll_layout_job", "SSE connection error", {
						job_id: jobId,
					});
					clearTimeout(timeout);
					es.close();
					resolve();
				};
			});
		},
		[applyLayoutFigures],
	);

	/** 指定ページ番号群をレイアウト解析ジョブキューへ投入する。 */
	const enqueueBatch = useCallback(
		async (
			paperId: string,
			batchPages: number[],
			fileHash: string | null,
			headers: HeadersInit,
		): Promise<{ jobId: string; streamUrl: string } | null> => {
			const formData = new URLSearchParams();
			formData.append("paper_id", paperId);
			formData.append("page_numbers", batchPages.join(","));
			if (fileHash) formData.append("file_hash", fileHash);
			if (sessionId) formData.append("session_id", sessionId);

			const response = await fetch(`${API_URL}/api/analyze-layout-lazy`, {
				method: "POST",
				headers,
				body: formData,
			});

			if (!response.ok) {
				log.error("enqueue_batch", "Enqueue failed", {
					pages: batchPages,
					status: response.status,
				});
				return null;
			}

			const result = await response.json();

			// Redis 未接続時のフォールバック: 即時結果が返る
			if (result.figures) {
				applyLayoutFigures(result.figures, paperId, fileHash);
				return null;
			}

			if (!result.job_id) return null;
			const streamUrl =
				result.stream_url ?? `/api/layout-jobs/${result.job_id}/stream`;
			return { jobId: result.job_id, streamUrl };
		},
		[sessionId, applyLayoutFigures],
	);

	/**
	 * 論文の全ページをレイアウト解析ジョブとしてキューに投入し、
	 * SSE ポーリングで結果を取得して pages に適用する。
	 */
	const triggerLazyLayoutAnalysis = useCallback(
		async (paperId: string, initialPages?: PageData[]) => {
			try {
				const finalPages = initialPages ?? [];
				if (!finalPages || finalPages.length === 0) return;

				const firstImgUrl = finalPages[0]?.image_url || "";
				const hashMatch = firstImgUrl.match(
					/\/static\/paper_images\/([^/]+)\//,
				);
				const fileHash = hashMatch ? hashMatch[1] : null;

				const headers = buildAuthHeaders(token, {
					"Content-Type": "application/x-www-form-urlencoded",
				});

				const pageNumbers = finalPages.map((p) => p.page_num);

				log.info("trigger_lazy_layout_analysis", "Enqueuing analysis job", {
					paper_id: paperId,
					total_pages: finalPages.length,
				});

				const job = await enqueueBatch(paperId, pageNumbers, fileHash, headers);
				const jobs = job ? [job] : [];

				await Promise.all(
					jobs.map(({ jobId, streamUrl }) =>
						pollLayoutJob(jobId, paperId, fileHash, streamUrl),
					),
				);

				log.info(
					"trigger_lazy_layout_analysis",
					"Completed lazy layout analysis",
				);
			} catch (err) {
				log.error(
					"trigger_lazy_layout_analysis",
					"Lazy layout analysis error",
					{
						error: err instanceof Error ? err.message : String(err),
					},
				);
				// Don't re-throw - this is a background enhancement, not critical
			}
		},
		[token, enqueueBatch, pollLayoutJob],
	);

	return { applyLayoutFigures, triggerLazyLayoutAnalysis };
}

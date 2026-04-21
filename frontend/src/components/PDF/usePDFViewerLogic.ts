import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";
import { createLogger } from "@/lib/logger";
import { useAuth } from "../../contexts/AuthContext";
import { usePaperCache } from "../../db/hooks";
import { useEvidenceHighlighting } from "../../hooks/useEvidenceHighlighting";
import { useLayoutPolling } from "../../hooks/useLayoutPolling";
import type { Grounding } from "../Chat/types";
import type { PageData } from "./types";
import { groupWordsIntoLines } from "./utils";

const log = createLogger("usePDFViewerLogic");

/**
 * Web Crypto API で File の SHA-256 ハッシュを計算する。
 * バックエンドの hashlib.sha256(bytes).hexdigest() と同値。
 */
export const computeFileHash = async (file: File): Promise<string> => {
	// Bypass hashing in tests to avoid jsdom/crypto hanging issues
	if (import.meta.env.VITEST) {
		return `test-hash-${file.name}-${file.size}`;
	}
	try {
		const buffer = await file.arrayBuffer();
		if (typeof crypto === "undefined" || !crypto.subtle) {
			log.warn("compute_file_hash", "Web Crypto Subtle API not available");
			return `dummy-${file.size}-${file.name}`;
		}
		const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
		return Array.from(new Uint8Array(hashBuffer))
			.map((b) => b.toString(16).padStart(2, "0"))
			.join("");
	} catch (e) {
		log.warn("compute_file_hash", "Web Crypto Hashing failed, using fallback", {
			error: e,
		});
		return `fallback-${file.size}`;
	}
};

export interface UsePDFViewerLogicProps {
	uploadFile?: File | null;
	paperId?: string | null;
	sessionId?: string;
	onStatusChange?: (
		status:
			| "idle"
			| "uploading"
			| "processing"
			| "layout_analysis"
			| "done"
			| "error",
	) => void;
	onPaperLoaded?: (paperId: string | null) => void;
	searchTerm?: string;
	onSearchMatchesUpdate?: (
		matches: Array<{ page: number; wordIndex: number }>,
	) => void;
	currentSearchMatch?: { page: number; wordIndex: number } | null;
	evidence?: Grounding;
	maxPdfSize?: number;
	mode?: "text" | "stamp" | "area" | "plaintext";
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
}

export function usePDFViewerLogic({
	uploadFile,
	paperId: propPaperId,
	sessionId,
	onStatusChange,
	onPaperLoaded,
	searchTerm,
	onSearchMatchesUpdate,
	currentSearchMatch,
	evidence,
	maxPdfSize = 50,
	mode: externalMode,
	jumpTarget,
}: UsePDFViewerLogicProps) {
	const { t, i18n } = useTranslation();
	const { token, getToken, isGuest } = useAuth();
	const {
		getCachedPaper,
		savePaperToCache,
		cachePaperImages,
		deleteCorruptedCache,
	} = usePaperCache();

	const [pages, setPages] = useState<PageData[]>([]);
	const [grobidText, setGrobidText] = useState<string | null>(null);
	const [status, setStatus] = useState<
		"idle" | "uploading" | "processing" | "layout_analysis" | "done" | "error"
	>("idle");
	const [errorMsg, setErrorMsg] = useState<string>("");
	const [uploadProgress, setUploadProgress] = useState<number>(0);
	const [loadedPaperId, setLoadedPaperId] = useState<string | null>(null);
	const [loadedPaperTitle, setLoadedPaperTitle] = useState<string | undefined>(
		undefined,
	);

	const eventSourceRef = useRef<EventSource | null>(null);
	const processingFileRef = useRef<File | null>(null);
	const activeTaskIdRef = useRef<string | null>(null);
	const pagesRef = useRef<PageData[]>([]);

	const [internalMode] = useState<"text" | "stamp" | "area" | "plaintext">(
		"plaintext",
	);
	const mode = externalMode ?? internalMode;
	const [hasMountedPdfMode, setHasMountedPdfMode] = useState(false);

	const currentVisiblePageRef = useRef<number>(1);
	const scrollProgressRef = useRef<{ page: number; ratio: number }>({
		page: 1,
		ratio: 0,
	});
	const scrollerRef = useRef<Element | null>(null);
	const pendingScrollRef = useRef<{ page: number; ratio: number } | null>(null);
	const prevModeRef = useRef(mode);

	const { evidenceHighlights } = useEvidenceHighlighting(evidence, pages);
	const { applyLayoutFigures, triggerLazyLayoutAnalysis } = useLayoutPolling({
		token,
		sessionId,
		getCachedPaper,
		savePaperToCache,
		setPages,
	});

	useEffect(() => {
		pagesRef.current = pages;
	}, [pages]);

	useEffect(() => {
		if (onStatusChange) {
			onStatusChange(status);
		}
	}, [status, onStatusChange]);

	useEffect(() => {
		if (mode !== "plaintext" && !hasMountedPdfMode) {
			setHasMountedPdfMode(true);
		}
	}, [mode, hasMountedPdfMode]);

	const handlePageVisible = useCallback((pageNum: number) => {
		currentVisiblePageRef.current = pageNum;
	}, []);

	useEffect(() => {
		const findScroller = () => {
			const prefix = mode === "plaintext" ? "text-page-" : "page-";
			const el = document.getElementById(`${prefix}1`);
			return el?.closest(".overflow-y-auto") ?? null;
		};
		const scroller = findScroller();
		scrollerRef.current = scroller;
		if (!scroller) return;

		const handleScroll = () => {
			const pageNum = currentVisiblePageRef.current;
			const prefix = mode === "plaintext" ? "text-page-" : "page-";
			const pageEl = document.getElementById(`${prefix}${pageNum}`);
			if (!pageEl) return;

			const scrollerRect = scroller.getBoundingClientRect();
			const pageRect = pageEl.getBoundingClientRect();
			const pageHeight = pageRect.height;
			if (pageHeight <= 0) return;

			const ratio = Math.max(
				0,
				Math.min(1, (scrollerRect.top - pageRect.top) / pageHeight),
			);
			scrollProgressRef.current = { page: pageNum, ratio };
		};

		scroller.addEventListener("scroll", handleScroll, { passive: true });
		return () => scroller.removeEventListener("scroll", handleScroll);
	}, [mode, pages]);

	const scrollToPageWithRatio = useCallback(
		(prefix: string, page: number, ratio: number) => {
			const rafId = requestAnimationFrame(() => {
				const targetEl = document.getElementById(`${prefix}${page}`);
				if (!targetEl) return;
				const scroller = targetEl.closest(".overflow-y-auto");
				if (scroller) {
					const currentScrollTop = scroller.scrollTop;
					const targetRect = targetEl.getBoundingClientRect();
					const scrollerRect = scroller.getBoundingClientRect();
					const pageTopInScroller =
						currentScrollTop + (targetRect.top - scrollerRect.top);
					const scrollOffset = ratio * targetEl.offsetHeight;
					scroller.scrollTo({
						top: pageTopInScroller + scrollOffset,
						behavior: "instant",
					});
				} else {
					targetEl.scrollIntoView({ block: "start" });
				}
			});
			return rafId;
		},
		[],
	);

	useEffect(() => {
		if (!hasMountedPdfMode || pendingScrollRef.current === null) return;
		const { page, ratio } = pendingScrollRef.current;
		pendingScrollRef.current = null;
		const rafId = scrollToPageWithRatio("page-", page, ratio);
		return () => cancelAnimationFrame(rafId);
	}, [hasMountedPdfMode, scrollToPageWithRatio]);

	useEffect(() => {
		const prevMode = prevModeRef.current;
		if (prevMode === mode) return;
		prevModeRef.current = mode;

		const { page: targetPage, ratio } = scrollProgressRef.current;
		const newPrefix = mode === "plaintext" ? "text-page-" : "page-";

		if (mode !== "plaintext" && !hasMountedPdfMode) {
			pendingScrollRef.current = { page: targetPage, ratio };
			return;
		}

		const rafId = scrollToPageWithRatio(newPrefix, targetPage, ratio);
		return () => cancelAnimationFrame(rafId);
	}, [mode, hasMountedPdfMode, scrollToPageWithRatio]);

	const searchMatches = useMemo(() => {
		if (!searchTerm || searchTerm.length < 2) return [];
		const lowerSearchTerm = searchTerm.toLowerCase();
		const matches: Array<{ page: number; wordIndex: number }> = [];
		pages.forEach((page) => {
			if (page.words) {
				page.words.forEach((word, wordIndex) => {
					if (word.word.toLowerCase().includes(lowerSearchTerm)) {
						matches.push({ page: page.page_num, wordIndex });
					}
				});
			}
		});
		return matches;
	}, [searchTerm, pages]);

	useEffect(() => {
		if (onSearchMatchesUpdate) {
			onSearchMatchesUpdate(searchMatches);
		}
	}, [searchMatches, onSearchMatchesUpdate]);

	useEffect(() => {
		if (!currentSearchMatch) return;

		const pageId =
			mode === "plaintext"
				? `text-page-${currentSearchMatch.page}`
				: `page-${currentSearchMatch.page}`;
		const pageEl = document.getElementById(pageId);
		if (!pageEl) return;

		const scroller = pageEl.closest(".overflow-y-auto");
		const matchEl = document.getElementById("current-search-match");

		if (scroller) {
			if (matchEl) {
				const matchRect = matchEl.getBoundingClientRect();
				const scrollerRect = scroller.getBoundingClientRect();
				const currentScrollTop = scroller.scrollTop;
				const matchTopInScroller =
					currentScrollTop + (matchRect.top - scrollerRect.top);
				scroller.scrollTo({
					top: matchTopInScroller - 100,
					behavior: "smooth",
				});
			} else {
				const pageRect = pageEl.getBoundingClientRect();
				const scrollerRect = scroller.getBoundingClientRect();
				const currentScrollTop = scroller.scrollTop;
				const pageTopInScroller =
					currentScrollTop + (pageRect.top - scrollerRect.top);
				scroller.scrollTo({ top: pageTopInScroller - 100, behavior: "smooth" });
			}
		} else {
			if (matchEl) {
				matchEl.scrollIntoView({ behavior: "smooth", block: "center" });
			} else {
				pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
			}
		}
	}, [currentSearchMatch, mode]);

	useEffect(() => {
		if (jumpTarget) {
			const pageId =
				mode === "plaintext"
					? `text-page-${jumpTarget.page}`
					: `page-${jumpTarget.page}`;
			const pageEl = document.getElementById(pageId);
			if (pageEl) {
				const scroller = pageEl.closest(".overflow-y-auto");
				if (scroller) {
					const pageRect = pageEl.getBoundingClientRect();
					const scrollerRect = scroller.getBoundingClientRect();
					const currentScrollTop = scroller.scrollTop;
					const pageTopInScroller =
						currentScrollTop + (pageRect.top - scrollerRect.top);
					const targetYInPage = pageRect.height * (jumpTarget.y || 0);
					const targetScrollTop =
						pageTopInScroller + targetYInPage - scrollerRect.height / 2;
					scroller.scrollTo({ top: targetScrollTop, behavior: "smooth" });
				} else {
					pageEl.scrollIntoView({ behavior: "smooth", block: "center" });
				}
			}
		}
	}, [jumpTarget, mode]);

	useEffect(() => {
		if (onPaperLoaded) {
			onPaperLoaded(loadedPaperId);
		}
		if (loadedPaperId) {
			getCachedPaper(loadedPaperId).then((cached) => {
				if (cached?.title) setLoadedPaperTitle(cached.title);
			});
		} else {
			setLoadedPaperTitle(undefined);
		}
	}, [loadedPaperId]);

	const checkFigureImagesExist = async (
		pages: PageData[],
	): Promise<boolean> => {
		for (const page of pages) {
			const firstFigure = page.figures?.[0];
			if (firstFigure?.image_url) {
				try {
					const res = await fetch(firstFigure.image_url, { method: "HEAD" });
					return res.ok;
				} catch {
					return false;
				}
			}
		}
		return true;
	};

	const fetchAndApplyDbFigures = async (
		paperId: string,
		fileHash: string | null,
	): Promise<boolean> => {
		try {
			const headers = buildAuthHeaders(token);
			const res = await fetch(`${API_URL}/api/papers/${paperId}/figures`, {
				headers,
			});
			if (!res.ok) return false;
			const data = await res.json();
			if (Array.isArray(data.figures) && data.figures.length > 0) {
				applyLayoutFigures(data.figures, paperId, fileHash);
				log.info(
					"load_existing_paper",
					"Loaded figures from DB, skipping layout analysis",
					{
						paper_id: paperId,
						count: data.figures.length,
					},
				);
				return true;
			}
			return false;
		} catch {
			return false;
		}
	};

	const uploadToGcsSigned = (file: File, signedUrl: string): Promise<void> =>
		new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			xhr.open("PUT", signedUrl);
			xhr.setRequestHeader("Content-Type", "application/pdf");
			xhr.upload.onprogress = (e) => {
				if (e.lengthComputable) {
					setUploadProgress(Math.round((e.loaded / e.total) * 100));
				}
			};
			xhr.onload = () =>
				xhr.status < 300
					? resolve()
					: reject(new Error(`GCS upload failed: ${xhr.status}`));
			xhr.onerror = () => reject(new Error("GCS upload network error"));
			xhr.send(file);
		});

	const _legacyAnalyzePdf = async (file: File, headers: HeadersInit) => {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("lang", i18n.language.startsWith("ja") ? "ja" : "en");
		formData.append("mode", "json");
		if (sessionId) {
			formData.append("session_id", sessionId);
		}
		const response = await fetch(`${API_URL}/api/analyze-pdf-json`, {
			method: "POST",
			headers,
			body: formData,
		});
		if (!response.ok) {
			if (response.status === 413) throw new Error("__file_too_large__");
			const errData = await response.json().catch(() => ({}));
			throw new Error(errData.error || "Upload failed");
		}
		const { task_id, stream_url } = await response.json();
		activeTaskIdRef.current = task_id;
		await startStreaming(stream_url, 0);
	};

	const startStreaming = async (stream_url: string, retryCount: number = 0) => {
		const maxRetries = 3;
		const retryDelay = 1000 * 2 ** retryCount;

		if (eventSourceRef.current) {
			eventSourceRef.current.close();
		}

		setStatus("processing");
		const fullStreamUrl = stream_url.startsWith("http")
			? stream_url
			: `${API_URL}${stream_url}`;
		const es = new EventSource(fullStreamUrl);
		eventSourceRef.current = es;

		es.onmessage = (event) => {
			try {
				const eventData = JSON.parse(event.data);
				if (eventData.type === "page") {
					setPages((prev) => {
						let newData = eventData.data;
						if (!newData || typeof newData.page_num === "undefined") {
							return prev;
						}
						if (
							newData.image_url &&
							!newData.image_url.startsWith("http") &&
							!newData.image_url.startsWith("blob:")
						) {
							newData = {
								...newData,
								image_url: `${API_URL}${newData.image_url}`,
							};
						}
						if (Array.isArray(newData.figures) && newData.figures.length > 0) {
							newData = {
								...newData,
								figures: newData.figures.map((f: any) => ({
									...f,
									image_url:
										f.image_url &&
										!f.image_url.startsWith("http") &&
										!f.image_url.startsWith("blob:")
											? `${API_URL}${f.image_url}`
											: f.image_url,
								})),
							};
						}
						const index = prev.findIndex(
							(p) => p.page_num === newData.page_num,
						);
						if (index !== -1) {
							const newPages = [...prev];
							newPages[index] = { ...newPages[index], ...newData };
							return newPages;
						}
						return [...prev, newData];
					});
				} else if (eventData.type === "done") {
					if (eventData.paper_id) {
						const pId = eventData.paper_id;
						setLoadedPaperId(pId);
						const finalPages = pagesRef.current || [];

						(async () => {
							const imageUrls = finalPages.map((p) => p.image_url);
							const ocrText = JSON.stringify(
								finalPages.map((p) => p.content || ""),
							);
							const layoutData = finalPages.map((p) => ({
								width: p.width,
								height: p.height,
								words: p.words,
								figures: p.figures,
								links: p.links,
							}));

							let fileHash = "";
							if (imageUrls.length > 0) {
								const match = imageUrls[0].match(
									/\/static\/paper_images\/([^/]+)\//,
								);
								if (match) fileHash = match[1];
							}

							await savePaperToCache({
								id: pId,
								file_hash: fileHash,
								title: processingFileRef.current?.name || "Untitled",
								ocr_text: ocrText,
								layout_json: JSON.stringify(layoutData),
								server_updated_at: Date.now(),
								last_accessed: Date.now(),
							});
							cachePaperImages(pId, imageUrls).catch(() => {
								/* Ignore error */
							});
						})();

						if (eventData.db_saved === false) {
							setStatus("done");
						} else {
							setStatus("layout_analysis");
							const layoutTimeout = setTimeout(
								() => setStatus("done"),
								135_000,
							);
							triggerLazyLayoutAnalysis(pId, finalPages)
								.catch(() => {})
								.finally(() => {
									clearTimeout(layoutTimeout);
									setStatus("done");
								});
						}
					} else {
						setStatus("done");
					}
					es.close();
					processingFileRef.current = null;
					activeTaskIdRef.current = null;
				} else if (eventData.type === "error") {
					setStatus("error");
					setErrorMsg(t("common.errors.processing"));
					es.close();
					processingFileRef.current = null;
					activeTaskIdRef.current = null;
				}
			} catch (_e) {
				// Ignored: JSON parse error or event mapping error
			}
		};

		es.onerror = () => {
			es.close();
			if (pagesRef.current.length > 0) {
				setStatus("done");
				processingFileRef.current = null;
				activeTaskIdRef.current = null;
				return;
			}
			if (retryCount < maxRetries) {
				setTimeout(() => {
					startStreaming(stream_url, retryCount + 1);
				}, retryDelay);
			} else {
				setStatus("error");
				setErrorMsg(t("common.errors.network"));
				processingFileRef.current = null;
				activeTaskIdRef.current = null;
			}
		};
	};

	const startAnalysis = async (file: File) => {
		if (processingFileRef.current === file) return;

		if (file.size > maxPdfSize * 1024 * 1024) {
			setStatus("error");
			setErrorMsg(t("common.errors.file_too_large", { maxMB: maxPdfSize }));
			return;
		}

		processingFileRef.current = file;
		setStatus("uploading");
		setUploadProgress(0);
		setPages([]);
		setGrobidText(null);
		setLoadedPaperId(null);

		try {
			const freshToken = await getToken().catch(() => null);
			const headers = buildAuthHeaders(freshToken ?? token);
			const lang = i18n.language.startsWith("ja") ? "ja" : "en";

			const fileHash = await computeFileHash(file);
			const urlRes = await fetch(
				`${API_URL}/api/pdf/request-upload-url?file_hash=${fileHash}&file_size_bytes=${file.size}`,
				{ headers },
			);

			if (!urlRes.ok) {
				if (urlRes.status === 413) {
					const errData = await urlRes.json().catch(() => ({}));
					const err = new Error("__file_too_large__") as Error & {
						maxMB?: number;
					};
					err.maxMB = errData.max_mb ?? maxPdfSize;
					throw err;
				}
				throw new Error("Upload request failed");
			}

			const { upload_url, already_cached } = await urlRes.json();

			if (upload_url == null) {
				await _legacyAnalyzePdf(file, headers);
				return;
			}

			if (!already_cached) {
				await uploadToGcsSigned(file, upload_url);
			}

			const analyzeRes = await fetch(`${API_URL}/api/pdf/analyze-pdf-hash`, {
				method: "POST",
				headers: {
					...(headers as Record<string, string>),
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					file_hash: fileHash,
					filename: file.name,
					lang,
					session_id: sessionId ?? null,
				}),
			});

			if (!analyzeRes.ok) {
				if (analyzeRes.status === 404) throw new Error("__upload_missing__");
				throw new Error("Analysis start failed");
			}

			const { task_id, stream_url } = await analyzeRes.json();
			activeTaskIdRef.current = task_id;
			await startStreaming(stream_url, 0);
		} catch (err: any) {
			setStatus("error");
			if (err?.message === "__file_too_large__") {
				setErrorMsg(
					t("common.errors.file_too_large", { maxMB: err.maxMB ?? maxPdfSize }),
				);
			} else {
				setErrorMsg(t("common.errors.upload_failed"));
			}
			processingFileRef.current = null;
			activeTaskIdRef.current = null;
		}
	};

	const loadExistingPaper = async (id: string) => {
		setStatus("processing");
		setLoadedPaperId(id);
		setGrobidText(null);

		try {
			const cached = await getCachedPaper(id);
			if (cached?.layout_json && cached.file_hash) {
				try {
					const layoutList = JSON.parse(cached.layout_json);
					let ocrParts: string[];
					try {
						const parsed = JSON.parse(cached.ocr_text || "[]");
						ocrParts = Array.isArray(parsed)
							? parsed
							: (cached.ocr_text || "").split("\n\n---\n\n");
					} catch {
						ocrParts = (cached.ocr_text || "").split("\n\n---\n\n");
					}
					const fileHash = cached.file_hash;
					const cachedPages: PageData[] = layoutList.map(
						(layout: any, i: number) => ({
							page_num: i + 1,
							image_url: `${API_URL}/static/paper_images/${fileHash}/page_${i + 1}.jpg`,
							width: layout?.width || 0,
							height: layout?.height || 0,
							words: layout?.words || [],
							figures: (layout?.figures || []).map((f: any) => ({
								...f,
								image_url:
									f.image_url &&
									!f.image_url.startsWith("http") &&
									!f.image_url.startsWith("blob:")
										? `${API_URL}${f.image_url}`
										: f.image_url,
							})),
							links: layout?.links || [],
							content: ocrParts[i] || "",
						}),
					);

					if (cachedPages.length > 0) {
						setPages(cachedPages);
						const hasFigures = cachedPages.some(
							(p) => p.figures && p.figures.length > 0,
						);
						const figuresOk =
							hasFigures && (await checkFigureImagesExist(cachedPages));
						if (!hasFigures || !figuresOk) {
							const pagesForAnalysis = hasFigures
								? cachedPages.map((p) => ({ ...p, figures: [] }))
								: cachedPages;
							if (hasFigures) {
								setPages(pagesForAnalysis);
							}
							const dbHasFigures = await fetchAndApplyDbFigures(
								id,
								cached.file_hash,
							);
							if (!dbHasFigures) {
								setStatus("layout_analysis");
								const layoutTimeoutCached = setTimeout(
									() => setStatus("done"),
									135_000,
								);
								triggerLazyLayoutAnalysis(id, pagesForAnalysis).finally(() => {
									clearTimeout(layoutTimeoutCached);
									setStatus("done");
								});
							} else {
								setStatus("done");
							}
						} else {
							setStatus("done");
						}

						if (sessionId) {
							const fd = new FormData();
							fd.append("session_id", sessionId);
							fd.append("paper_id", id);
							fetch(`${API_URL}/api/session-context`, {
								method: "POST",
								headers: buildAuthHeaders(token),
								body: fd,
							}).catch(() => {});
						}

						(async () => {
							try {
								const bgRes = await fetch(`${API_URL}/api/papers/${id}`, {
									headers: buildAuthHeaders(token),
								});
								if (!bgRes.ok) return;
								const bgData = await bgRes.json();
								const serverTs = bgData.updated_at
									? new Date(bgData.updated_at).getTime()
									: 0;
								const cachedTs = cached.server_updated_at ?? 0;
								if (serverTs <= cachedTs) return;

								if (bgData.layout_json && bgData.file_hash) {
									const bgLayoutList = JSON.parse(bgData.layout_json);
									let bgOcrParts: string[];
									try {
										const bgParsed = JSON.parse(bgData.ocr_text || "[]");
										bgOcrParts = Array.isArray(bgParsed)
											? bgParsed
											: (bgData.ocr_text || "").split("\n\n---\n\n");
									} catch {
										bgOcrParts = (bgData.ocr_text || "").split("\n\n---\n\n");
									}
									const bgPages: PageData[] = bgLayoutList.map(
										(layout: any, i: number) => ({
											page_num: i + 1,
											image_url: `${API_URL}/static/paper_images/${bgData.file_hash}/page_${i + 1}.jpg`,
											width: layout?.width || 0,
											height: layout?.height || 0,
											words: layout?.words || [],
											figures: (layout?.figures || []).map((f: any) => ({
												...f,
												image_url:
													f.image_url &&
													!f.image_url.startsWith("http") &&
													!f.image_url.startsWith("blob:")
														? `${API_URL}${f.image_url}`
														: f.image_url,
											})),
											links: layout?.links || [],
											content: bgOcrParts[i] || "",
										}),
									);
									if (bgPages.length > 0) {
										setPages(bgPages);
										if (!isGuest) {
											await savePaperToCache({
												...cached,
												layout_json: bgData.layout_json,
												ocr_text: bgData.ocr_text,
												server_updated_at: serverTs,
												last_accessed: Date.now(),
											});
										}
									}
								}
							} catch (_bgErr) {
								/* Ignore background catch */
							}
						})();
						return;
					}
				} catch (_e) {
					await deleteCorruptedCache(id);
				}
			}

			const headers = buildAuthHeaders(token);
			const paperRes = await fetch(`${API_URL}/api/papers/${id}`, { headers });
			if (paperRes.ok) {
				const paperData = await paperRes.json();
				if (!isGuest) {
					await savePaperToCache({
						id: id,
						file_hash: paperData.file_hash || "",
						title: paperData.title || paperData.filename,
						ocr_text: paperData.ocr_text,
						layout_json: (() => {
							if (!paperData.layout_json) return paperData.layout_json;
							try {
								const parsed = JSON.parse(paperData.layout_json);
								const normalized = parsed.map((page: any) => ({
									...page,
									figures: (page.figures || []).map((f: any) => ({
										...f,
										image_url:
											f.image_url &&
											!f.image_url.startsWith("http") &&
											!f.image_url.startsWith("blob:")
												? `${API_URL}${f.image_url}`
												: f.image_url,
									})),
								}));
								return JSON.stringify(normalized);
							} catch {
								return paperData.layout_json;
							}
						})(),
						full_summary: paperData.full_summary,
						section_summary_json: paperData.section_summary_json,
						server_updated_at: paperData.updated_at
							? new Date(paperData.updated_at).getTime()
							: Date.now(),
						last_accessed: Date.now(),
					});
				}

				if (paperData.layout_json && paperData.file_hash) {
					try {
						const layoutList = JSON.parse(paperData.layout_json);
						let ocrParts: string[];
						try {
							const ocrParsed = JSON.parse(paperData.ocr_text || "[]");
							ocrParts = Array.isArray(ocrParsed)
								? ocrParsed
								: (paperData.ocr_text || "").split("\n\n---\n\n");
						} catch {
							ocrParts = (paperData.ocr_text || "").split("\n\n---\n\n");
						}
						const fileHash = paperData.file_hash;
						if (paperData.grobid_text) {
							setGrobidText(paperData.grobid_text);
						}
						const fullPages: PageData[] = layoutList.map(
							(layout: any, i: number) => ({
								page_num: i + 1,
								image_url: `${API_URL}/static/paper_images/${fileHash}/page_${i + 1}.jpg`,
								width: layout?.width || 0,
								height: layout?.height || 0,
								words: layout?.words || [],
								figures: (layout?.figures || []).map((f: any) => ({
									...f,
									image_url:
										f.image_url &&
										!f.image_url.startsWith("http") &&
										!f.image_url.startsWith("blob:")
											? `${API_URL}${f.image_url}`
											: f.image_url,
								})),
								links: layout?.links || [],
								content: ocrParts[i] || "",
							}),
						);

						if (fullPages.length > 0) {
							setPages(fullPages);
							cachePaperImages(
								id,
								fullPages.map((p) => p.image_url),
							).catch(() => {});
							const hasFigures = fullPages.some(
								(p) => p.figures && p.figures.length > 0,
							);
							const figuresOk =
								hasFigures && (await checkFigureImagesExist(fullPages));
							if (!hasFigures || !figuresOk) {
								const pagesForAnalysis = hasFigures
									? fullPages.map((p) => ({ ...p, figures: [] }))
									: fullPages;
								if (hasFigures) setPages(pagesForAnalysis);
								const dbHasFigures = await fetchAndApplyDbFigures(
									id,
									paperData.file_hash,
								);
								if (!dbHasFigures) {
									setStatus("layout_analysis");
									const layoutTimeoutFull = setTimeout(
										() => setStatus("done"),
										135_000,
									);
									triggerLazyLayoutAnalysis(id, pagesForAnalysis).finally(
										() => {
											clearTimeout(layoutTimeoutFull);
											setStatus("done");
										},
									);
								} else {
									setStatus("done");
								}
							} else {
								setStatus("done");
							}

							if (sessionId) {
								const fd = new FormData();
								fd.append("session_id", sessionId);
								fd.append("paper_id", id);
								fetch(`${API_URL}/api/session-context`, {
									method: "POST",
									headers: buildAuthHeaders(token),
									body: fd,
								}).catch(() => {
									/* Ignore sync error */
								});
							}
							return;
						}
					} catch (_parseErr) {
						/* Ignore fallback to load API */
					}
				}
			}

			const formData = new FormData();
			if (sessionId) formData.append("session_id", sessionId);

			const response = await fetch(`${API_URL}/api/analyze-paper/${id}`, {
				method: "POST",
				headers,
				body: formData,
			});

			if (!response.ok) throw new Error("Failed to load paper");

			const data = await response.json();
			const { stream_url } = data;

			const fullStreamUrl = stream_url.startsWith("http")
				? stream_url
				: `${API_URL}${stream_url}`;
			const es = new EventSource(fullStreamUrl);
			eventSourceRef.current = es;

			es.onmessage = (event) => {
				try {
					const eventData = JSON.parse(event.data);
					if (eventData.type === "page") {
						setPages((prev) => {
							const newData = eventData.data;
							const index = prev.findIndex(
								(p) => p.page_num === newData.page_num,
							);
							if (index !== -1) {
								const newPages = [...prev];
								newPages[index] = { ...newPages[index], ...newData };
								return newPages;
							}
							return [...prev, newData];
						});
					} else if (eventData.type === "done") {
						setStatus("done");
						es.close();
					} else if (eventData.type === "error") {
						setStatus("error");
						setErrorMsg(t("common.errors.processing"));
						es.close();
					}
				} catch (_e) {
					/* Ignore partial json parsing errors */
				}
			};

			es.onerror = () => {
				es.close();
				if (pages.length === 0) setStatus("error");
			};
		} catch (_err: any) {
			setStatus("error");
			setErrorMsg(t("common.errors.network"));
		}
	};

	useEffect(() => {
		let isMounted = true;
		const initiate = async () => {
			if (!isMounted) return;
			if (uploadFile) {
				startAnalysis(uploadFile);
			} else if (propPaperId && propPaperId !== loadedPaperId) {
				loadExistingPaper(propPaperId);
			}
		};
		initiate();
		return () => {
			isMounted = false;
			if (eventSourceRef.current && !activeTaskIdRef.current) {
				eventSourceRef.current.close();
				eventSourceRef.current = null;
			}
		};
	}, [uploadFile, propPaperId]);

	const pagesWithLines = useMemo(() => {
		if (grobidText) {
			const firstPage = pages[0];
			return [
				{
					page_num: 1,
					content: grobidText,
					lines: [],
					words: [],
					figures: firstPage?.figures || [],
					links: firstPage?.links || [],
					image_url: firstPage?.image_url || "",
					width: firstPage?.width || 0,
					height: firstPage?.height || 0,
				},
			];
		}
		return groupWordsIntoLines(pages);
	}, [pages, grobidText]);

	return {
		pages,
		pagesWithLines,
		status,
		errorMsg,
		uploadProgress,
		loadedPaperId,
		loadedPaperTitle,
		hasMountedPdfMode,
		mode,
		evidenceHighlights,
		handlePageVisible,
	};
}

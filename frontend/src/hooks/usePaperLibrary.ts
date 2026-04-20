import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import { getUICache, setUICache, usePaperCache } from "../db/hooks";
import { db, isDbAvailable } from "../db/index";

const log = createLogger("usePaperLibrary");

export type Paper = {
	paper_id: string;
	title?: string;
	filename?: string;
	created_at: string;
};

type UsePaperLibraryDeps = {
	userId: string | undefined;
	token: string | null;
	isGuest: boolean;
};

export function usePaperLibrary({
	userId,
	token,
	isGuest,
}: UsePaperLibraryDeps) {
	const [uploadedPapers, setUploadedPapers] = useState<Paper[]>([]);
	const [isPapersLoading, setIsPapersLoading] = useState(false);
	const { deletePaperCache } = usePaperCache();

	// 認証済みユーザーの論文一覧を取得 (stale-while-revalidate)
	useEffect(() => {
		if (!userId || !token) {
			setUploadedPapers([]);
			setIsPapersLoading(false);
			return;
		}

		const cacheKey = `paper_list:${userId}`;
		const load = async () => {
			// キャッシュがあれば即座に表示（スケルトンなし）
			const cached = await getUICache<Paper[]>(cacheKey);
			if (cached) {
				setUploadedPapers(cached);
				setIsPapersLoading(false);
			} else {
				setIsPapersLoading(true);
			}

			// バックグラウンドでAPI取得・キャッシュ更新
			for (let attempt = 0; attempt < 3; attempt++) {
				try {
					const res = await fetch(`${API_URL}/api/papers`, {
						headers: { Authorization: `Bearer ${token}` },
						signal: AbortSignal.timeout(30000),
					});
					const data = await res.json();
					const papers = Array.isArray(data.papers) ? data.papers : [];
					setUploadedPapers(papers);
					await setUICache(cacheKey, papers);
					setIsPapersLoading(false);
					return;
				} catch (err) {
					if (attempt < 2) {
						await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
					} else {
						log.error("fetch_papers", "Failed to fetch papers", { error: err });
						if (!cached) {
							setUploadedPapers([]);
							setIsPapersLoading(false);
						}
					}
				}
			}
		};
		load();
	}, [userId, token]);

	// ゲストユーザーの論文一覧を IndexedDB から取得
	useEffect(() => {
		if (!isGuest) return;
		setIsPapersLoading(true);
		const loadGuestPapers = async () => {
			if (!isDbAvailable()) {
				setUploadedPapers([]);
				setIsPapersLoading(false);
				return;
			}
			try {
				const cached = await db.papers
					.orderBy("last_accessed")
					.reverse()
					.toArray();
				setUploadedPapers(
					cached.map((p) => ({
						paper_id: p.id,
						title: p.title,
						filename: p.title,
						created_at: new Date(p.last_accessed).toISOString(),
					})),
				);
			} catch {
				setUploadedPapers([]);
			} finally {
				setIsPapersLoading(false);
			}
		};
		loadGuestPapers();
	}, [isGuest]);

	const refreshPapers = useCallback(async () => {
		if (isGuest) {
			if (!isDbAvailable()) return;
			setIsPapersLoading(true);
			try {
				const cached = await db.papers
					.orderBy("last_accessed")
					.reverse()
					.toArray();
				setUploadedPapers(
					cached.map((p) => ({
						paper_id: p.id,
						title: p.title,
						filename: p.title,
						created_at: new Date(p.last_accessed).toISOString(),
					})),
				);
			} catch {
				// ignore
			} finally {
				setIsPapersLoading(false);
			}
		} else {
			// スケルトンなし（アップロード後のサイレント更新）
			if (!token || !userId) return;
			try {
				const res = await fetch(`${API_URL}/api/papers`, {
					headers: { Authorization: `Bearer ${token}` },
				});
				const data = await res.json();
				const papers = Array.isArray(data?.papers) ? data.papers : [];
				setUploadedPapers(papers);
				await setUICache(`paper_list:${userId}`, papers);
			} catch (err) {
				log.error("refresh_papers", "Failed to refresh papers", { error: err });
			}
		}
	}, [isGuest, token, userId]);

	/** 論文を削除する。削除した論文が currentPaperId と一致していた場合 true を返す */
	const deletePaper = useCallback(
		async (
			paper: { paper_id: string },
			currentPaperId: string | null,
			userObj: { id?: string } | null,
		) => {
			if (userObj && token) {
				try {
					await fetch(`${API_URL}/api/papers/${paper.paper_id}`, {
						method: "DELETE",
						headers: { Authorization: `Bearer ${token}` },
					});
				} catch (err) {
					log.error("delete_paper", "Failed to delete paper from DB", {
						error: err,
					});
				}
			}
			await deletePaperCache(paper.paper_id);
			if (userId) {
				const cacheKey = `paper_list:${userId}`;
				const cached = await getUICache<Paper[]>(cacheKey);
				if (cached) {
					await setUICache(
						cacheKey,
						cached.filter((p) => p.paper_id !== paper.paper_id),
					);
				}
			}
			setUploadedPapers((prev) =>
				prev.filter((p) => p.paper_id !== paper.paper_id),
			);
			return currentPaperId === paper.paper_id;
		},
		[token, userId, deletePaperCache],
	);

	return {
		uploadedPapers,
		setUploadedPapers,
		isPapersLoading,
		setIsPapersLoading,
		refreshPapers,
		deletePaper,
	};
}

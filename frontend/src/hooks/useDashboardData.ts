import { useCallback, useEffect, useState } from "react";
import { getUICache, setUICache, useBookmarks } from "@/db/hooks";
import type { Bookmark } from "@/db/index";
import {
	deletePaper as deletePaperApi,
	fetchUserPapers,
	fetchUserPersona,
	fetchUserStats,
	fetchUserTranslations,
	type PaperEntry,
	type TranslationEntry,
	type UserPersona,
	type UserStats,
} from "@/lib/dashboard";
import { createLogger } from "@/lib/logger";

const log = createLogger("useDashboardData");

export const TRANSLATIONS_PER_PAGE = 20;

async function revalidate<T>(
	cacheKey: string,
	fetcher: () => Promise<T | null>,
	onData: (v: T) => void,
	onLoading?: (v: boolean) => void,
): Promise<void> {
	const cached = await getUICache<T>(cacheKey);
	if (cached) {
		onData(cached);
	} else {
		onLoading?.(true);
	}
	try {
		const fresh = await fetcher();
		if (fresh != null) {
			onData(fresh);
			await setUICache(cacheKey, fresh);
		}
	} catch (e) {
		log.error("revalidate", `Failed for ${cacheKey}`, { e });
	} finally {
		onLoading?.(false);
	}
}

export function useDashboardData(
	token: string | null,
	userId: string | undefined,
) {
	const { getBookmarks, deleteBookmark } = useBookmarks();

	const [stats, setStats] = useState<UserStats | null>(null);
	const [statsLoading, setStatsLoading] = useState(false);
	const [papers, setPapers] = useState<PaperEntry[]>([]);
	const [papersLoading, setPapersLoading] = useState(false);
	const [persona, setPersona] = useState<UserPersona | null>(null);
	const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
	const [translations, setTranslations] = useState<TranslationEntry[]>([]);
	const [totalTranslations, setTotalTranslations] = useState(0);
	const [translationsLoading, setTranslationsLoading] = useState(false);
	const [translationPage, setTranslationPage] = useState(1);

	useEffect(() => {
		if (!token || !userId) return;
		revalidate(
			`dashboard_stats:${userId}`,
			() => fetchUserStats(token),
			setStats,
			setStatsLoading,
		);
		revalidate(
			`dashboard_papers:${userId}`,
			() => fetchUserPapers(token, 100).then((r) => r.papers),
			setPapers,
			setPapersLoading,
		);
		revalidate(
			`dashboard_persona:${userId}`,
			() => fetchUserPersona(token),
			setPersona,
		);
		getBookmarks().then(setBookmarks);
	}, [token, userId, getBookmarks]);

	useEffect(() => {
		if (!token) return;
		setTranslationsLoading(true);
		fetchUserTranslations(token, translationPage, TRANSLATIONS_PER_PAGE)
			.then((res) => {
				setTranslations(res.translations);
				setTotalTranslations(res.total);
			})
			.catch((e) =>
				log.error("fetch_translations", "Failed to fetch translations", { e }),
			)
			.finally(() => setTranslationsLoading(false));
	}, [token, translationPage]);

	const removePaper = useCallback(
		async (paperId: string) => {
			if (!token) return;
			await deletePaperApi(token, paperId);
			setPapers((prev) => prev.filter((x) => x.paper_id !== paperId));
			if (userId) {
				const key = `dashboard_papers:${userId}`;
				const cached = await getUICache<PaperEntry[]>(key);
				if (cached)
					await setUICache(
						key,
						cached.filter((x) => x.paper_id !== paperId),
					);
			}
		},
		[token, userId],
	);

	const removeBookmark = useCallback(
		async (id: number) => {
			await deleteBookmark(id);
			setBookmarks((prev) => prev.filter((b) => b.id !== id));
		},
		[deleteBookmark],
	);

	return {
		stats,
		statsLoading,
		papers,
		papersLoading,
		removePaper,
		persona,
		bookmarks,
		removeBookmark,
		translations,
		totalTranslations,
		translationsLoading,
		translationPage,
		setTranslationPage,
		totalPages: Math.ceil(totalTranslations / TRANSLATIONS_PER_PAGE),
	};
}

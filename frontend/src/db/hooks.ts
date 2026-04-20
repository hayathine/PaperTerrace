import { useCallback } from "react";
import { createLogger } from "@/lib/logger";
import {
	type Bookmark,
	db,
	evictIfOverQuota,
	type ImageCache,
	isDbAvailable,
	type PaperCache,
} from "./index";

const log = createLogger("DBHooks");

/**
 * Fetch an image and store it as a Blob in IndexedDB.
 * Returns null on any failure (network, quota, etc.) without throwing.
 */
async function fetchAndCacheImage(
	imageUrl: string,
	paperId: string,
	label: "figure" | "table" | "page" | "formula",
): Promise<ImageCache | null> {
	if (!isDbAvailable()) return null;
	try {
		const response = await fetch(imageUrl);
		if (!response.ok) return null;
		const blob = await response.blob();

		const entry: ImageCache = {
			id: imageUrl,
			paper_id: paperId,
			blob,
			label,
			created_at: Date.now(),
		};

		await db.images.put(entry);
		return entry;
	} catch (e) {
		// Handle QuotaExceededError specifically
		if (isQuotaError(e)) {
			log.warn(
				"fetch_and_cache_image",
				"Storage quota exceeded while caching image, evicting old data...",
			);

			await evictIfOverQuota();
		} else {
			log.error("fetch_and_cache_image", "Failed to fetch and cache image", {
				imageUrl,
				error: e,
			});
		}
		return null;
	}
}

/**
 * Check if an error is a storage quota exceeded error.
 */
function isQuotaError(e: unknown): boolean {
	if (e instanceof DOMException && e.name === "QuotaExceededError") return true;
	if (e instanceof Error && e.message.includes("quota")) return true;
	return false;
}

export function usePaperCache() {
	const getCachedPaper = useCallback(
		async (paperId: string): Promise<PaperCache | undefined> => {
			if (!isDbAvailable()) return undefined;
			try {
				return await db.papers.get(paperId);
			} catch (e) {
				log.warn("get_cached_paper", "Failed to read paper cache", {
					error: e,
				});

				return undefined;
			}
		},
		[],
	);

	const savePaperToCache = useCallback(async (paper: PaperCache) => {
		if (!isDbAvailable()) return;
		try {
			await db.papers.put(paper);
		} catch (e) {
			if (isQuotaError(e)) {
				log.warn(
					"save_paper_to_cache",
					"Quota exceeded while saving paper, evicting...",
				);

				await evictIfOverQuota();
				// Retry once after eviction
				try {
					await db.papers.put(paper);
				} catch {
					log.warn("save_paper_to_cache", "Retry after eviction also failed");
				}
			} else {
				log.error("save_paper_to_cache", "Failed to save paper cache", {
					error: e,
				});
			}
		}
	}, []);

	const getCachedImage = useCallback(
		async (imageUrl: string): Promise<ImageCache | undefined> => {
			if (!isDbAvailable()) return undefined;
			try {
				return await db.images.get(imageUrl);
			} catch (e) {
				log.warn("get_cached_image", "Failed to read image cache", {
					error: e,
				});

				return undefined;
			}
		},
		[],
	);

	const saveImageToCache = useCallback(async (image: ImageCache) => {
		if (!isDbAvailable()) return;
		try {
			await db.images.put(image);
		} catch (e) {
			if (isQuotaError(e)) {
				await evictIfOverQuota();
			}
			log.warn("save_image_to_cache", "Failed to save image cache", {
				error: e,
			});
		}
	}, []);

	const deletePaperCache = useCallback(async (paperId: string) => {
		if (!isDbAvailable()) return;
		try {
			await db.papers.delete(paperId);
			await db.images.where("paper_id").equals(paperId).delete();
		} catch (e) {
			log.error("delete_paper_cache", "Failed to delete paper cache", {
				error: e,
			});
		}
	}, []);

	const cachePaperImages = useCallback(
		async (paperId: string, pageUrls: string[]) => {
			if (!isDbAvailable()) return [];
			const CONCURRENCY = 3;
			const results: (ImageCache | null)[] = [];
			let next = 0;
			const worker = async () => {
				while (next < pageUrls.length) {
					const i = next++;
					results[i] = await fetchAndCacheImage(pageUrls[i], paperId, "page");
				}
			};
			await Promise.all(
				Array.from({ length: Math.min(CONCURRENCY, pageUrls.length) }, worker),
			);
			return results;
		},
		[],
	);

	/**
	 * Delete a corrupted paper cache entry.
	 * Call this when cached layout_json fails to parse, etc.
	 */
	const deleteCorruptedCache = useCallback(async (paperId: string) => {
		if (!isDbAvailable()) return;
		try {
			await db.papers.delete(paperId);
			log.warn("delete_corrupted_cache", "Deleted corrupted cache for paper", {
				paperId,
			});
		} catch (e) {
			log.error("delete_corrupted_cache", "Failed to delete corrupted cache", {
				error: e,
			});
		}
	}, []);

	return {
		getCachedPaper,
		savePaperToCache,
		getCachedImage,
		saveImageToCache,
		deletePaperCache,
		cachePaperImages,
		deleteCorruptedCache,
	};
}

export function useBookmarks() {
	const addBookmark = useCallback(
		async (paperId: string, paperTitle: string, pageNumber: number) => {
			if (!isDbAvailable()) return;
			try {
				// 同じページのしおりが既にあれば削除（トグル）
				const existing = await db.bookmarks
					.where({ paper_id: paperId, page_number: pageNumber })
					.first();
				if (existing?.id != null) {
					await db.bookmarks.delete(existing.id);
					return false; // 削除した
				}
				await db.bookmarks.add({
					paper_id: paperId,
					paper_title: paperTitle,
					page_number: pageNumber,
					created_at: Date.now(),
				});
				return true; // 追加した
			} catch (e) {
				log.error("add_bookmark", "Failed to add bookmark", { error: e });
				return false;
			}
		},
		[],
	);

	const getBookmarks = useCallback(async (): Promise<Bookmark[]> => {
		if (!isDbAvailable()) return [];
		try {
			return await db.bookmarks.orderBy("created_at").reverse().toArray();
		} catch (e) {
			log.error("get_bookmarks", "Failed to get bookmarks", { error: e });
			return [];
		}
	}, []);

	const getPageBookmarks = useCallback(
		async (paperId: string, pageNumber: number): Promise<boolean> => {
			if (!isDbAvailable()) return false;
			try {
				const bm = await db.bookmarks
					.where({ paper_id: paperId, page_number: pageNumber })
					.first();
				return bm != null;
			} catch {
				return false;
			}
		},
		[],
	);

	const deleteBookmark = useCallback(async (id: number) => {
		if (!isDbAvailable()) return;
		try {
			await db.bookmarks.delete(id);
		} catch (e) {
			log.error("delete_bookmark", "Failed to delete bookmark", { error: e });
		}
	}, []);

	return { addBookmark, getBookmarks, getPageBookmarks, deleteBookmark };
}

export async function getUICache<T>(key: string): Promise<T | null> {
	if (!isDbAvailable()) return null;
	try {
		const entry = await db.ui_cache.get(key);
		if (!entry) return null;
		return JSON.parse(entry.data) as T;
	} catch (e) {
		log.warn("get_ui_cache", "Failed to read UI cache", { key, error: e });
		return null;
	}
}

export async function setUICache<T>(key: string, data: T): Promise<void> {
	if (!isDbAvailable()) return;
	try {
		await db.ui_cache.put({
			key,
			data: JSON.stringify(data),
			cached_at: Date.now(),
		});
	} catch (e) {
		log.warn("set_ui_cache", "Failed to write UI cache", { key, error: e });
	}
}

export async function removeUICache(key: string): Promise<void> {
	if (!isDbAvailable()) return;
	try {
		await db.ui_cache.delete(key);
	} catch (e) {
		log.warn("remove_ui_cache", "Failed to remove UI cache", { key, error: e });
	}
}

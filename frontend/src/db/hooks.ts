import { useCallback } from "react";
import {
	db,
	evictIfOverQuota,
	type ImageCache,
	isDbAvailable,
	type PaperCache,
} from "./index";

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
			console.warn(
				"Storage quota exceeded while caching image, evicting old data...",
			);
			await evictIfOverQuota();
		} else {
			console.error("Failed to fetch and cache image:", imageUrl, e);
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
				console.warn("Failed to read paper cache:", e);
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
				console.warn("Quota exceeded while saving paper, evicting...");
				await evictIfOverQuota();
				// Retry once after eviction
				try {
					await db.papers.put(paper);
				} catch {
					console.warn("Retry after eviction also failed");
				}
			} else {
				console.error("Failed to save paper cache:", e);
			}
		}
	}, []);

	const getCachedImage = useCallback(
		async (imageUrl: string): Promise<ImageCache | undefined> => {
			if (!isDbAvailable()) return undefined;
			try {
				return await db.images.get(imageUrl);
			} catch (e) {
				console.warn("Failed to read image cache:", e);
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
			console.warn("Failed to save image cache:", e);
		}
	}, []);

	const deletePaperCache = useCallback(async (paperId: string) => {
		if (!isDbAvailable()) return;
		try {
			await db.papers.delete(paperId);
			await db.images.where("paper_id").equals(paperId).delete();
		} catch (e) {
			console.error("Failed to delete paper cache:", e);
		}
	}, []);

	const cachePaperImages = useCallback(
		async (paperId: string, pageUrls: string[]) => {
			if (!isDbAvailable()) return [];
			return Promise.all(
				pageUrls.map((url) => fetchAndCacheImage(url, paperId, "page")),
			);
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
			console.warn(`Deleted corrupted cache for paper: ${paperId}`);
		} catch (e) {
			console.error("Failed to delete corrupted cache:", e);
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

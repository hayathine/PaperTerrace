import { db, type PaperCache, type ImageCache } from "./index";
import { useCallback } from "react";

/**
 * Fetch an image and store it as a Blob in IndexedDB.
 */
async function fetchAndCacheImage(
  imageUrl: string,
  paperId: string,
  label: "figure" | "table" | "page" | "formula",
) {
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
    console.error("Failed to fetch and cache image:", imageUrl, e);
    return null;
  }
}

export function usePaperCache() {
  const getCachedPaper = useCallback(async (paperId: string) => {
    return await db.papers.get(paperId);
  }, []);

  const savePaperToCache = useCallback(async (paper: PaperCache) => {
    await db.papers.put(paper);
  }, []);

  const getCachedImage = useCallback(async (imageUrl: string) => {
    return await db.images.get(imageUrl);
  }, []);

  const saveImageToCache = useCallback(async (image: ImageCache) => {
    await db.images.put(image);
  }, []);

  const deletePaperCache = useCallback(async (paperId: string) => {
    await db.papers.delete(paperId);
    await db.images.where("paper_id").equals(paperId).delete();
  }, []);

  const cachePaperImages = useCallback(
    async (paperId: string, pageUrls: string[]) => {
      return Promise.all(
        pageUrls.map((url) => fetchAndCacheImage(url, paperId, "page")),
      );
    },
    [],
  );

  return {
    getCachedPaper,
    savePaperToCache,
    getCachedImage,
    saveImageToCache,
    deletePaperCache,
    cachePaperImages,
  };
}

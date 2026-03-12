import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePaperCache } from "./hooks";
import { db, isDbAvailable } from "./index";

vi.mock("./index", async (importOriginal) => {
	const actual: any = await importOriginal();
	return {
		...actual,
		isDbAvailable: vi.fn().mockReturnValue(true),
		evictIfOverQuota: vi.fn().mockResolvedValue(undefined),
		db: {
			papers: {
				get: vi.fn(),
				put: vi.fn(),
				delete: vi.fn(),
			},
			images: {
				get: vi.fn(),
				put: vi.fn(),
				where: vi.fn().mockReturnThis(),
				equals: vi.fn().mockReturnThis(),
				delete: vi.fn(),
			},
		},
	};
});

describe("usePaperCache", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(isDbAvailable).mockReturnValue(true);
	});

	it("should return undefined if DB is not available", async () => {
		vi.mocked(isDbAvailable).mockReturnValue(false);
		const { result } = renderHook(() => usePaperCache());

		const paper = await result.current.getCachedPaper("p1");
		expect(paper).toBeUndefined();
		expect(db.papers.get).not.toHaveBeenCalled();
	});

	it("should get a cached paper", async () => {
		const mockPaper = { id: "p1", title: "Test" };
		vi.mocked(db.papers.get).mockResolvedValue(mockPaper as any);

		const { result } = renderHook(() => usePaperCache());
		const paper = await result.current.getCachedPaper("p1");

		expect(paper).toEqual(mockPaper);
		expect(db.papers.get).toHaveBeenCalledWith("p1");
	});

	it("should save a paper to cache", async () => {
		const mockPaper = { id: "p1", title: "Test", last_accessed: 123 } as any;

		const { result } = renderHook(() => usePaperCache());
		await result.current.savePaperToCache(mockPaper);

		expect(db.papers.put).toHaveBeenCalledWith(mockPaper);
	});

	it("should delete paper cache", async () => {
		const { result } = renderHook(() => usePaperCache());
		await result.current.deletePaperCache("p1");

		expect(db.papers.delete).toHaveBeenCalledWith("p1");
		expect(db.images.where).toHaveBeenCalledWith("paper_id");
	});

	it("should fetch and cache images", async () => {
		const mockBlob = new Blob(["test"], { type: "image/png" });
		const globalFetch = vi.fn().mockResolvedValue({
			ok: true,
			blob: vi.fn().mockResolvedValue(mockBlob),
		});
		vi.stubGlobal("fetch", globalFetch);

		const { result } = renderHook(() => usePaperCache());
		const results = await result.current.cachePaperImages("p1", ["url1"]);

		expect(globalFetch).toHaveBeenCalledWith("url1");
		expect(db.images.put).toHaveBeenCalled();
		expect(results[0]).not.toBeNull();
	});
});

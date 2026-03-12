import { beforeEach, describe, expect, it, vi } from "vitest";
import { db, evictIfOverQuota, initDB, isDbAvailable } from "./index";

vi.mock("dexie", () => {
	const MockDexie = vi.fn().mockImplementation(() => {
		const instance: any = {
			version: vi.fn().mockReturnThis(),
			stores: vi.fn().mockImplementation((stores) => {
				Object.keys(stores).forEach((key) => {
					instance[key] = {
						orderBy: vi.fn().mockReturnThis(),
						limit: vi.fn().mockReturnThis(),
						toArray: vi.fn().mockResolvedValue([]),
						delete: vi.fn().mockResolvedValue(undefined),
						where: vi.fn().mockReturnThis(),
						equals: vi.fn().mockReturnThis(),
						count: vi.fn().mockResolvedValue(0),
						put: vi.fn().mockResolvedValue(undefined),
						get: vi.fn().mockResolvedValue(undefined),
					};
				});
				return instance;
			}),
			open: vi.fn().mockResolvedValue(undefined),
		};
		return instance;
	});
	return { default: MockDexie };
});

describe("DB Index", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should initialize the database successfully", async () => {
		const available = await initDB();
		expect(available).toBe(true);
		expect(isDbAvailable()).toBe(true);
		expect(db.open).toHaveBeenCalled();
	});

	it("should handle initialization failure", async () => {
		vi.mocked(db.open).mockRejectedValueOnce(new Error("DB Error"));
		const available = await initDB();
		expect(available).toBe(false);
		expect(isDbAvailable()).toBe(false);
	});

	it("should evict papers if over quota", async () => {
		await initDB(); // ensure dbAvailable is true
		// Mock navigator.storage.estimate
		const mockEstimate = vi.fn().mockResolvedValue({
			usage: 1000 * 1024 * 1024, // 1000MB (limit is 500MB)
			quota: 2000 * 1024 * 1024,
		});

		Object.defineProperty(navigator, "storage", {
			value: { estimate: mockEstimate },
			configurable: true,
		});

		const mockPapers = [
			{ id: "p1", last_accessed: 100 },
			{ id: "p2", last_accessed: 200 },
		];

		vi.mocked(
			db.papers.orderBy("last_accessed").limit(5).toArray,
		).mockResolvedValueOnce(mockPapers as any);

		await evictIfOverQuota();

		expect(mockEstimate).toHaveBeenCalled();
		expect(db.papers.delete).toHaveBeenCalledWith("p1");
		expect(db.papers.delete).toHaveBeenCalledWith("p2");
		expect(db.images.where).toHaveBeenCalledWith("paper_id");
	});

	it("should not evict if under quota", async () => {
		await initDB(); // ensure dbAvailable is true
		const mockEstimate = vi.fn().mockResolvedValue({
			usage: 100 * 1024 * 1024, // 100MB
			quota: 2000 * 1024 * 1024,
		});

		Object.defineProperty(navigator, "storage", {
			value: { estimate: mockEstimate },
			configurable: true,
		});

		await evictIfOverQuota();

		expect(db.papers.delete).not.toHaveBeenCalled();
	});
});

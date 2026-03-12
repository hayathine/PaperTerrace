import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { db, isDbAvailable } from "./index";
import { recordEdit, useSyncStatus } from "./sync";

vi.mock("./index", async (importOriginal) => {
	const actual: any = await importOriginal();
	return {
		...actual,
		isDbAvailable: vi.fn().mockReturnValue(true),
		db: {
			edit_history: {
				where: vi.fn().mockReturnThis(),
				equals: vi.fn().mockReturnThis(),
				count: vi.fn().mockResolvedValue(0),
				add: vi.fn().mockResolvedValue(1),
			},
		},
	};
});

describe("DB Sync", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
		vi.mocked(isDbAvailable).mockReturnValue(true);

		// Default online
		Object.defineProperty(navigator, "onLine", {
			value: true,
			configurable: true,
		});
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("should show offline status when navigator is offline", () => {
		Object.defineProperty(navigator, "onLine", {
			value: false,
			configurable: true,
		});

		const { result } = renderHook(() => useSyncStatus());
		expect(result.current).toBe("offline");
	});

	it("should check sync status periodically", async () => {
		vi.mocked(db.edit_history.count).mockResolvedValue(0);

		const { result } = renderHook(() => useSyncStatus());
		expect(result.current).toBe("synced");

		vi.mocked(db.edit_history.count).mockResolvedValue(2);

		await act(async () => {
			vi.advanceTimersByTime(5000);
		});

		expect(result.current).toBe("pending");
	});

	it("should record an edit success", async () => {
		await recordEdit("p1", "note", { text: "hello" });

		expect(db.edit_history.add).toHaveBeenCalledWith(
			expect.objectContaining({
				paper_id: "p1",
				type: "note",
				synced: false,
			}),
		);
	});

	it("should not record edit if DB is unavailable", async () => {
		vi.mocked(isDbAvailable).mockReturnValue(false);

		await recordEdit("p1", "note", { text: "hello" });
		expect(db.edit_history.add).not.toHaveBeenCalled();
	});
});

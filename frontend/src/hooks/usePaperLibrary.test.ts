import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePaperLibrary } from "./usePaperLibrary";

// Mock dependencies
vi.mock("@/lib/logger", () => ({
	createLogger: () => ({
		error: vi.fn(),
		info: vi.fn(),
		warn: vi.fn(),
		debug: vi.fn(),
	}),
}));

vi.mock("../db/hooks", () => ({
	usePaperCache: () => ({
		deletePaperCache: vi.fn().mockResolvedValue(undefined),
	}),
}));

vi.mock("../db/index", () => ({
	db: {
		papers: {
			orderBy: vi.fn().mockReturnThis(),
			reverse: vi.fn().mockReturnThis(),
			toArray: vi
				.fn()
				.mockResolvedValue([
					{ id: "guest-1", title: "Guest Paper", last_accessed: Date.now() },
				]),
		},
	},
	isDbAvailable: vi.fn().mockReturnValue(true),
}));

// Mock AbortSignal.timeout if it doesn't exist or to control it
if (typeof AbortSignal !== "undefined" && !AbortSignal.timeout) {
	(AbortSignal as any).timeout = vi
		.fn()
		.mockReturnValue(new AbortController().signal);
}

describe("usePaperLibrary", () => {
	const props = {
		userId: "user-1",
		token: "token-1",
		isGuest: false,
	};

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("should fetch papers for authenticated users on mount", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({
				papers: [
					{ paper_id: "p1", title: "Paper 1", created_at: "2024-01-01" },
				],
			}),
		});

		const { result } = renderHook(() => usePaperLibrary(props));

		// Wait for useEffect
		await act(async () => {
			await new Promise((r) => setTimeout(r, 0));
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/papers"),
			expect.any(Object),
		);
		expect(result.current.uploadedPapers).toHaveLength(1);
		expect(result.current.uploadedPapers[0].paper_id).toBe("p1");
	});

	it("should load papers from IndexedDB for guest users", async () => {
		const { result } = renderHook(() =>
			usePaperLibrary({
				...props,
				userId: undefined,
				token: null,
				isGuest: true,
			}),
		);

		await act(async () => {
			await new Promise((r) => setTimeout(r, 0));
		});

		expect(result.current.uploadedPapers).toHaveLength(1);
		expect(result.current.uploadedPapers[0].paper_id).toBe("guest-1");
		expect(result.current.uploadedPapers[0].title).toBe("Guest Paper");
	});

	it("should retry fetch on failure", async () => {
		(global.fetch as any)
			.mockRejectedValueOnce(new Error("Timeout"))
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ papers: [] }),
			});

		vi.useFakeTimers();

		renderHook(() => usePaperLibrary(props));

		// Advance timers and await microtasks
		await act(async () => {
			await vi.advanceTimersByTimeAsync(2000);
		});

		expect(global.fetch).toHaveBeenCalledTimes(2);
	});

	it("should delete paper and update state", async () => {
		// Mock initial fetch to return 2 papers
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => ({
				papers: [
					{ paper_id: "p1", title: "P1", created_at: "..." },
					{ paper_id: "p2", title: "P2", created_at: "..." },
				],
			}),
		});

		const { result } = renderHook(() => usePaperLibrary(props));

		// Wait for initial load
		await act(async () => {
			await new Promise((r) => setTimeout(r, 0));
		});

		expect(result.current.uploadedPapers).toHaveLength(2);

		// Now mock the DELETE call
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => ({}),
		});

		let wasCurrent: boolean = false;
		await act(async () => {
			wasCurrent = await result.current.deletePaper({ paper_id: "p1" }, "p1", {
				id: "user-1",
			});
		});

		expect(wasCurrent).toBe(true);
		expect(result.current.uploadedPapers).toHaveLength(1);
		expect(result.current.uploadedPapers[0].paper_id).toBe("p2");
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/papers/p1"),
			expect.objectContaining({ method: "DELETE" }),
		);
	});
});

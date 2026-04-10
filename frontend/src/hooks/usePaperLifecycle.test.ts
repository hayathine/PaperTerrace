import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { syncTrajectory } from "../lib/recommendation";
import { usePaperLifecycle } from "./usePaperLifecycle";

// Mock syncTrajectory
vi.mock("../lib/recommendation", () => ({
	syncTrajectory: vi.fn(),
}));

describe("usePaperLifecycle", () => {
	const sessionId = "test-session";
	const token = "test-token";

	beforeEach(() => {
		vi.useFakeTimers();
		vi.clearAllMocks();
		// Mock sendBeacon
		Object.defineProperty(navigator, "sendBeacon", {
			value: vi.fn().mockReturnValue(true),
			configurable: true,
		});
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("should track session duration and delete cache when switching papers", () => {
		const { rerender } = renderHook(
			({ paperId }) => usePaperLifecycle(paperId, sessionId, token),
			{
				initialProps: { paperId: "paper-1" as string | null },
			},
		);

		// Advance time by 5 seconds
		act(() => {
			vi.advanceTimersByTime(5000);
		});

		// Switch to paper-2
		rerender({ paperId: "paper-2" });

		// Check if duration was synced for paper-1
		expect(syncTrajectory).toHaveBeenCalledWith(
			expect.objectContaining({
				paper_id: "paper-1",
				session_duration: 5,
			}),
			token,
		);

		// Check if cache delete was called for paper-1
		expect(navigator.sendBeacon).toHaveBeenCalledWith(
			expect.stringContaining("/api/chat/cache/delete"),
			expect.any(FormData),
		);

		const formData = (navigator.sendBeacon as any).mock.calls[0][1];
		expect(formData.get("paper_id")).toBe("paper-1");
	});

	it("should delete cache and sync duration on beforeunload", () => {
		renderHook(() => usePaperLifecycle("paper-3", sessionId, token));

		act(() => {
			vi.advanceTimersByTime(10000);
		});

		// Simulate beforeunload
		window.dispatchEvent(new Event("beforeunload"));

		expect(syncTrajectory).toHaveBeenCalledWith(
			expect.objectContaining({
				paper_id: "paper-3",
				session_duration: 10,
			}),
			token,
		);

		expect(navigator.sendBeacon).toHaveBeenCalled();
	});
});

// Helper act for timers if needed (though vitest standard act should work)
function act(callback: () => void) {
	callback();
}

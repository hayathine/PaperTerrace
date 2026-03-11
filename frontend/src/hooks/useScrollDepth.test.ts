import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useScrollDepth } from "./useScrollDepth";

describe("useScrollDepth", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Define global gtag if it doesn't exist
		(global as any).gtag = vi.fn();

		// Mock window properties
		Object.defineProperty(window, "innerHeight", {
			value: 1000,
			writable: true,
		});
		Object.defineProperty(window, "scrollY", { value: 0, writable: true });

		// Mock document.documentElement properties
		Object.defineProperty(document.documentElement, "scrollHeight", {
			value: 4000,
			writable: true,
		});
	});

	it("should trigger gtag event when scrolling past thresholds", () => {
		renderHook(({ paperId }) => useScrollDepth(paperId), {
			initialProps: { paperId: "paper-1" },
		});

		// Scroll to 25% (scrollBottom = 1000, scrollHeight = 4000)
		// Wait, scrollBottom = scrollY + innerHeight. So for 1000, scrollY = 0.
		// 1000 / 4000 = 25%.

		// Trigger scroll event manually
		window.dispatchEvent(new Event("scroll"));

		expect((global as any).gtag).toHaveBeenCalledWith("event", "scroll_depth", {
			threshold_percent: 25,
			paper_id: "paper-1",
		});

		// Scroll more to 50%
		(window as any).scrollY = 1000; // scrollBottom = 2000 / 4000 = 50%
		window.dispatchEvent(new Event("scroll"));

		expect((global as any).gtag).toHaveBeenCalledWith("event", "scroll_depth", {
			threshold_percent: 50,
			paper_id: "paper-1",
		});
	});

	it("should not trigger the same threshold twice", () => {
		renderHook(() => useScrollDepth("paper-1"));

		window.dispatchEvent(new Event("scroll"));
		expect((global as any).gtag).toHaveBeenCalledTimes(1); // 25%

		window.dispatchEvent(new Event("scroll"));
		expect((global as any).gtag).toHaveBeenCalledTimes(1); // Still 1
	});

	it("should reset thresholds when paperIdentifier changes", () => {
		const { rerender } = renderHook(({ paperId }) => useScrollDepth(paperId), {
			initialProps: { paperId: "paper-1" },
		});

		window.dispatchEvent(new Event("scroll"));
		expect((global as any).gtag).toHaveBeenCalledWith("event", "scroll_depth", {
			threshold_percent: 25,
			paper_id: "paper-1",
		});

		// Change paper
		rerender({ paperId: "paper-2" });

		// Clear mock to check new calls
		(global as any).gtag.mockClear();

		window.dispatchEvent(new Event("scroll"));
		expect((global as any).gtag).toHaveBeenCalledWith("event", "scroll_depth", {
			threshold_percent: 25,
			paper_id: "paper-2",
		});
	});
});

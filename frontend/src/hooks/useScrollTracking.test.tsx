import { renderHook } from "@testing-library/react";
import { logEvent } from "firebase/analytics";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useScrollTracking } from "./useScrollTracking";

vi.mock("firebase/analytics", () => ({
	logEvent: vi.fn(),
	getAnalytics: vi.fn(),
}));

vi.mock("@/lib/firebase", () => ({
	analytics: {},
}));

describe("useScrollTracking", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should log event when reaching 50% threshold", () => {
		const { result } = renderHook(() => useScrollTracking("paper1"));
		const handleScroll = result.current;

		// 50% threshold should trigger 10, 25, 50
		const mockEvent50 = {
			currentTarget: {
				scrollTop: 250,
				clientHeight: 250,
				scrollHeight: 1000,
			},
		} as unknown as React.UIEvent<HTMLDivElement>;

		handleScroll(mockEvent50);

		expect(logEvent).toHaveBeenCalledWith(expect.anything(), "scroll", {
			percent_scrolled: 10,
			paper_id: "paper1",
		});
		expect(logEvent).toHaveBeenCalledWith(expect.anything(), "scroll", {
			percent_scrolled: 25,
			paper_id: "paper1",
		});
		expect(logEvent).toHaveBeenCalledWith(expect.anything(), "scroll", {
			percent_scrolled: 50,
			paper_id: "paper1",
		});
	});

	it("should log multiple thresholds only once", () => {
		const { result } = renderHook(() => useScrollTracking("paper1"));
		const handleScroll = result.current;

		const mockEvent25 = {
			currentTarget: {
				scrollTop: 0,
				clientHeight: 250,
				scrollHeight: 1000,
			},
		} as unknown as React.UIEvent<HTMLDivElement>;

		handleScroll(mockEvent25);
		expect(logEvent).toHaveBeenCalledWith(expect.anything(), "scroll", {
			percent_scrolled: 25,
			paper_id: "paper1",
		});

		vi.clearAllMocks();
		handleScroll(mockEvent25);
		expect(logEvent).not.toHaveBeenCalled();
	});

	it("should not log when analytics or paperId is missing", () => {
		const { result } = renderHook(() => useScrollTracking(null));
		const handleScroll = result.current;

		const mockEvent = {
			currentTarget: {
				scrollTop: 500,
				clientHeight: 500,
				scrollHeight: 1000,
			},
		} as unknown as React.UIEvent<HTMLDivElement>;

		handleScroll(mockEvent);
		expect(logEvent).not.toHaveBeenCalled();
	});
});

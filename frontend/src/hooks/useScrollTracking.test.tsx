import { renderHook } from "@testing-library/react";
import { beforeEach, describe, it, vi } from "vitest";
import { useScrollTracking } from "./useScrollTracking";

describe("useScrollTracking", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should render and handle scroll without error", () => {
		const { result } = renderHook(() => useScrollTracking("paper1"));
		const handleScroll = result.current;

		const mockEvent50 = {
			currentTarget: {
				scrollTop: 250,
				clientHeight: 250,
				scrollHeight: 1000,
			},
		} as unknown as React.UIEvent<HTMLDivElement>;

		// Should not throw
		handleScroll(mockEvent50);
	});

	it("should handle missing paperId without error", () => {
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
	});
});

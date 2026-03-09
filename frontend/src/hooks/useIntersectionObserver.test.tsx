import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useIntersectionObserver } from "./useIntersectionObserver";

describe("useIntersectionObserver", () => {
	it("returns false initially", () => {
		// Arrange
		const mockRef = { current: document.createElement("div") };
		const mockObserver = vi.fn((_callback) => ({
			observe: vi.fn(),
			disconnect: vi.fn(),
		}));
		vi.stubGlobal("IntersectionObserver", mockObserver);

		// Act
		const { result } = renderHook(() => useIntersectionObserver(mockRef));

		// Assert
		expect(result.current).toBe(false);
	});

	it("updates to true when entry is intersecting", () => {
		// Arrange
		const mockRef = { current: document.createElement("div") };
		let observerCallback: (entries: any[]) => void = () => {};

		const mockObserver = vi.fn((callback) => {
			observerCallback = callback;
			return {
				observe: vi.fn(),
				disconnect: vi.fn(),
			};
		});
		vi.stubGlobal("IntersectionObserver", mockObserver);

		// Act
		const { result } = renderHook(() => useIntersectionObserver(mockRef));

		// Simulate intersection
		act(() => {
			observerCallback([{ isIntersecting: true }]);
		});

		// Assert
		expect(result.current).toBe(true);
	});

	it("disconnects on unmount", () => {
		// Arrange
		const mockRef = { current: document.createElement("div") };
		const disconnect = vi.fn();

		const mockObserver = vi.fn(() => ({
			observe: vi.fn(),
			disconnect: disconnect,
		}));
		vi.stubGlobal("IntersectionObserver", mockObserver);

		// Act
		const { unmount } = renderHook(() => useIntersectionObserver(mockRef));
		unmount();

		// Assert
		expect(disconnect).toHaveBeenCalled();
	});
});

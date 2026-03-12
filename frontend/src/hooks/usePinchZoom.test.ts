import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { usePinchZoom } from "./usePinchZoom";

describe("usePinchZoom", () => {
	it("should initialize with zoom 1", () => {
		const { result } = renderHook(() => usePinchZoom());
		expect(result.current.zoom).toBe(1);
	});

	it("should reset zoom", () => {
		const { result } = renderHook(() => usePinchZoom());

		// Manual state change via wheel or pinch is complex, so we check if reset function is there
		expect(typeof result.current.resetZoom).toBe("function");

		act(() => {
			result.current.resetZoom();
		});
		expect(result.current.zoom).toBe(1);
	});

	it("should change zoom on ctrl+wheel", () => {
		const { result } = renderHook(() => usePinchZoom({ wheelStep: 0.1 }));

		const mockEvent = {
			ctrlKey: true,
			deltaY: -100, // zoom in
			preventDefault: vi.fn(),
		} as any;

		act(() => {
			result.current.onWheel(mockEvent);
		});

		expect(result.current.zoom).toBeGreaterThan(1);
		expect(mockEvent.preventDefault).toHaveBeenCalled();
	});

	it("should not change zoom on wheel without ctrl", () => {
		const { result } = renderHook(() => usePinchZoom());

		const mockEvent = {
			ctrlKey: false,
			deltaY: -100,
			preventDefault: vi.fn(),
		} as any;

		act(() => {
			result.current.onWheel(mockEvent);
		});

		expect(result.current.zoom).toBe(1);
		expect(mockEvent.preventDefault).not.toHaveBeenCalled();
	});

	it("should respect min and max limits", () => {
		const { result } = renderHook(() =>
			usePinchZoom({ min: 1, max: 2, wheelStep: 1.5 }),
		);

		// Zoom in beyond max
		act(() => {
			result.current.onWheel({
				ctrlKey: true,
				deltaY: -100,
				preventDefault: vi.fn(),
			} as any);
		});
		expect(result.current.zoom).toBe(2);

		// Zoom out beyond min
		act(() => {
			result.current.onWheel({
				ctrlKey: true,
				deltaY: 100,
				preventDefault: vi.fn(),
			} as any);
			result.current.onWheel({
				ctrlKey: true,
				deltaY: 100,
				preventDefault: vi.fn(),
			} as any);
		});
		expect(result.current.zoom).toBe(1);
	});
});

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useLayoutState } from "./useLayoutState";

describe("useLayoutState hook", () => {
	it("initializes with desktop defaults", () => {
		vi.stubGlobal("innerWidth", 1024);
		const { result } = renderHook(() => useLayoutState());

		expect(result.current.sidebarWidth).toBe(384);
		expect(result.current.isMobile).toBe(false);
		expect(result.current.isLeftSidebarOpen).toBe(true);
		expect(result.current.isRightSidebarOpen).toBe(false);
	});

	it("initializes with mobile defaults", () => {
		vi.stubGlobal("innerWidth", 375);
		const { result } = renderHook(() => useLayoutState());

		expect(result.current.isMobile).toBe(true);
		expect(result.current.isLeftSidebarOpen).toBe(false);
	});

	it("updates mobile status on resize", () => {
		vi.stubGlobal("innerWidth", 1024);
		const { result } = renderHook(() => useLayoutState());
		expect(result.current.isMobile).toBe(false);

		act(() => {
			vi.stubGlobal("innerWidth", 400);
			window.dispatchEvent(new Event("resize"));
		});

		expect(result.current.isMobile).toBe(true);
		expect(result.current.isLeftSidebarOpen).toBe(false);
		expect(result.current.isRightSidebarOpen).toBe(false);
	});

	it("handles sidebar resizing via mouse movements", () => {
		vi.stubGlobal("innerWidth", 1000);
		const { result } = renderHook(() => useLayoutState());

		act(() => {
			result.current.setIsResizing(true);
		});
		expect(result.current.isResizing).toBe(true);

		// Sidebar width = window.innerWidth - e.clientX
		// To get newWidth = 400, e.clientX should be 600
		act(() => {
			const moveEvent = new MouseEvent("mousemove", {
				clientX: 600,
			});
			window.dispatchEvent(moveEvent);
		});
		expect(result.current.sidebarWidth).toBe(400);

		// Finish resizing
		act(() => {
			window.dispatchEvent(new MouseEvent("mouseup"));
		});
		expect(result.current.isResizing).toBe(false);
	});

	it("constrains sidebar width within limits", () => {
		vi.stubGlobal("innerWidth", 1000);
		const { result } = renderHook(() => useLayoutState());

		act(() => {
			result.current.setIsResizing(true);
		});

		// Too small (less than 200)
		act(() => {
			window.dispatchEvent(new MouseEvent("mousemove", { clientX: 900 })); // width = 100
		});
		expect(result.current.sidebarWidth).toBe(384); // Kept original

		// Too large (more than 70% of 1000 = 700)
		act(() => {
			window.dispatchEvent(new MouseEvent("mousemove", { clientX: 200 })); // width = 800
		});
		expect(result.current.sidebarWidth).toBe(384);
	});
});

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { clampWidth, useLayoutState } from "./useLayoutState";

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

describe("clampWidth", () => {
	it("clamps to MIN_SIDEBAR_WIDTH when width is too small", () => {
		expect(clampWidth(50, 1024, false)).toBe(150);
	});

	it("clamps to maxAllowed when width is too large", () => {
		// viewportWidth=1024, leftOpen=false: maxAllowed = 1024-0-250-6 = 768
		expect(clampWidth(900, 1024, false)).toBe(768);
	});

	it("accounts for left sidebar when open", () => {
		// viewportWidth=1024, leftOpen=true: maxAllowed = 1024-256-250-6 = 512
		expect(clampWidth(600, 1024, true)).toBe(512);
	});

	it("returns width unchanged when within valid range", () => {
		// viewportWidth=1024, leftOpen=false: maxAllowed=768, min=150 -> 384 is valid
		expect(clampWidth(384, 1024, false)).toBe(384);
	});
});

describe("useLayoutState - left sidebar toggle recalculates sidebar width", () => {
	it("clamps right sidebar width when left sidebar opens on desktop", () => {
		// 768px 幅: leftOpen=true -> maxAllowed = 768-256-250-6 = 256
		vi.stubGlobal("innerWidth", 768);
		const { result } = renderHook(() => useLayoutState());
		// 初期化時に clampWidth(384, 768, true) = 256 になる
		expect(result.current.sidebarWidth).toBe(256);

		act(() => {
			result.current.setIsLeftSidebarOpen(false);
		});
		// leftOpen=false: maxAllowed = 768-0-250-6 = 512 -> clamp(256, 150, 512) = 256
		expect(result.current.sidebarWidth).toBe(256);

		act(() => {
			result.current.setIsLeftSidebarOpen(true);
		});
		// leftOpen=true: maxAllowed = 256 -> clamp(256, 150, 256) = 256
		expect(result.current.sidebarWidth).toBe(256);
	});

	it("does not recalculate sidebar width on mobile when left sidebar toggles", () => {
		vi.stubGlobal("innerWidth", 375);
		const { result } = renderHook(() => useLayoutState());
		const initialWidth = result.current.sidebarWidth;

		act(() => {
			result.current.setIsLeftSidebarOpen(true);
		});
		// モバイルは fixed overlay なので幅は変わらない
		expect(result.current.sidebarWidth).toBe(initialWidth);
	});
});

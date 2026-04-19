/** @vitest-environment jsdom */
import { fireEvent, renderHook } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// @ts-expect-error: IS_REACT_ACT_ENVIRONMENT is not defined in NodeJS.Global
global.IS_REACT_ACT_ENVIRONMENT = true;

import { useTextSelection } from "./useTextSelection";

describe("useTextSelection hook", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		// Mock document.getElementById
		const mockContainer = document.createElement("div");
		mockContainer.id = "text-page-1";
		mockContainer.getBoundingClientRect = vi.fn(() => ({
			left: 0,
			top: 0,
			width: 1000,
			height: 1000,
			right: 1000,
			bottom: 1000,
		})) as any;
		document.body.appendChild(mockContainer);

		return () => {
			document.body.removeChild(mockContainer);
		};
	});

	it("initializes with null selection menu", () => {
		const { result } = renderHook(() => useTextSelection(1));
		expect(result.current.selectionMenu).toBeNull();
	});

	it("sets selection menu when text is selected", () => {
		const { result } = renderHook(() => useTextSelection(1));

		const mockSelection = {
			toString: () => "Selected Text",
			rangeCount: 1,
			getRangeAt: () => ({
				startContainer: document.getElementById("text-page-1"),
				getBoundingClientRect: () => ({
					left: 100,
					top: 100,
					right: 200,
					bottom: 150,
					width: 100,
					height: 50,
				}),
			}),
		};
		vi.stubGlobal("getSelection", () => mockSelection);

		fireEvent.mouseUp(document);
		act(() => {
			vi.advanceTimersByTime(11);
		});

		expect(result.current.selectionMenu).not.toBeNull();
		expect(result.current.selectionMenu?.text).toBe("Selected Text");
	});

	it("clears selection menu when text is deselected", () => {
		const { result } = renderHook(() => useTextSelection(1));

		vi.stubGlobal("getSelection", () => ({
			toString: () => "Selected Text",
			rangeCount: 1,
			getRangeAt: () => ({
				startContainer: document.getElementById("text-page-1"),
				getBoundingClientRect: () => ({
					left: 100,
					top: 100,
					right: 200,
					bottom: 150,
					width: 100,
					height: 50,
				}),
			}),
		}));

		fireEvent.mouseUp(document);
		act(() => {
			vi.advanceTimersByTime(11);
		});
		expect(result.current.selectionMenu).not.toBeNull();

		vi.stubGlobal("getSelection", () => ({
			toString: () => "",
			rangeCount: 0,
		}));

		fireEvent.mouseUp(document);
		act(() => {
			vi.advanceTimersByTime(11);
		});

		expect(result.current.selectionMenu).toBeNull();
	});

	it("clears selection menu on click outside", () => {
		const { result } = renderHook(() => useTextSelection(1));

		vi.stubGlobal("getSelection", () => ({
			toString: () => "Selected Text",
			rangeCount: 1,
			getRangeAt: () => ({
				startContainer: document.getElementById("text-page-1"),
				getBoundingClientRect: () => ({
					left: 100,
					top: 100,
					right: 200,
					bottom: 150,
					width: 100,
					height: 50,
				}),
			}),
		}));

		fireEvent.mouseUp(document);
		act(() => {
			vi.advanceTimersByTime(11);
		});

		act(() => {
			fireEvent.mouseDown(document.body);
		});

		expect(result.current.selectionMenu).toBeNull();
	});
});

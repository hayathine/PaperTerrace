import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useWordInteraction } from "./useWordInteraction";

describe("useWordInteraction", () => {
	it("should initialize with undefined states", () => {
		const { result } = renderHook(() => useWordInteraction());

		expect(result.current.translationWord).toBeUndefined();
		expect(result.current.selectedWord).toBeUndefined();
		expect(result.current.explanationWord).toBeUndefined();
		expect(result.current.jumpTarget).toBeNull();
	});

	it("should update translation states via setTranslation", () => {
		const { result } = renderHook(() => useWordInteraction());
		const coords = { page: 1, x: 100, y: 200 };

		act(() => {
			result.current.setTranslation(
				"hello",
				"context hello world",
				coords,
				0.95,
			);
		});

		expect(result.current.translationWord).toBe("hello");
		expect(result.current.translationContext).toBe("context hello world");
		expect(result.current.translationCoordinates).toEqual(coords);
		expect(result.current.translationConf).toBe(0.95);
	});

	it("should update and truncate text selection", () => {
		const { result } = renderHook(() => useWordInteraction());
		const coords = { page: 2, x: 50, y: 50 };
		const longText =
			"This is a very long text that should be truncated by the hook implementation.";

		act(() => {
			result.current.setTextSelection(longText, coords);
		});

		// implementation truncates at 40 chars and adds ...
		expect(result.current.selectedWord).toBe(
			"This is a very long text that should...",
		);
		expect(result.current.selectedContext).toBe(`> ${longText}\n\n`);
		expect(result.current.selectedCoordinates).toEqual(coords);
	});

	it("should update area selection for figures", () => {
		const { result } = renderHook(() => useWordInteraction());
		const coords = { page: 3, x: 10, y: 10 };
		const imageUrl = "data:image/png;base64,...";

		act(() => {
			result.current.setAreaSelection(imageUrl, coords);
		});

		expect(result.current.selectedWord).toBe("Figure clipping (Page 3)");
		expect(result.current.selectedImage).toBe(imageUrl);
		expect(result.current.selectedCoordinates).toEqual(coords);
	});

	it("should update explanation states", () => {
		const { result } = renderHook(() => useWordInteraction());
		const coords = { page: 1, x: 0, y: 0 };

		act(() => {
			result.current.setExplanation("AI Prompt", "Full context string", coords);
		});

		expect(result.current.explanationWord).toBe("AI Prompt");
		expect(result.current.explanationContext).toBe("Full context string");
		expect(result.current.explanationCoordinates).toEqual(coords);
	});

	it("should reset all states via resetWordState", () => {
		const { result } = renderHook(() => useWordInteraction());

		act(() => {
			result.current.setTranslation("test", "ctx", { page: 1, x: 0, y: 0 });
			result.current.setExplanation("ai", "ctx", { page: 1, x: 0, y: 0 });
		});

		expect(result.current.translationWord).toBe("test");

		act(() => {
			result.current.resetWordState();
		});

		expect(result.current.translationWord).toBeUndefined();
		expect(result.current.explanationWord).toBeUndefined();
		expect(result.current.selectedWord).toBeUndefined();
		expect(result.current.pendingChatPrompt).toBeNull();
	});
});

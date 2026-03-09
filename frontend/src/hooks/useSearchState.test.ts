import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSearchState } from "./useSearchState";

describe("useSearchState hook", () => {
	it("initializes with default values", () => {
		const { result } = renderHook(() => useSearchState(true));

		expect(result.current.isSearchOpen).toBe(false);
		expect(result.current.searchTerm).toBe("");
		expect(result.current.searchMatches).toEqual([]);
		expect(result.current.currentMatchIndex).toBe(0);
	});

	it("toggles search modal", () => {
		const { result } = renderHook(() => useSearchState(true));

		act(() => {
			result.current.setIsSearchOpen(true);
		});
		expect(result.current.isSearchOpen).toBe(true);

		act(() => {
			result.current.handleCloseSearch();
		});
		expect(result.current.isSearchOpen).toBe(false);
	});

	it("navigates through search matches correctly", () => {
		const { result } = renderHook(() => useSearchState(true));
		const mockMatches = [
			{ page: 1, wordIndex: 10 },
			{ page: 1, wordIndex: 25 },
			{ page: 2, wordIndex: 5 },
		];

		act(() => {
			result.current.handleSearchMatchesUpdate(mockMatches);
		});
		expect(result.current.searchMatches).toHaveLength(3);
		expect(result.current.currentMatchIndex).toBe(0);
		expect(result.current.currentSearchMatch).toEqual(mockMatches[0]);

		act(() => {
			result.current.handleNextMatch();
		});
		expect(result.current.currentMatchIndex).toBe(1);

		act(() => {
			result.current.handleNextMatch();
		});
		expect(result.current.currentMatchIndex).toBe(2);

		// Circular navigation
		act(() => {
			result.current.handleNextMatch();
		});
		expect(result.current.currentMatchIndex).toBe(0);

		// Previous match
		act(() => {
			result.current.handlePrevMatch();
		});
		expect(result.current.currentMatchIndex).toBe(2);
	});

	it("resets state when search is closed", () => {
		const { result } = renderHook(() => useSearchState(true));

		act(() => {
			result.current.setSearchTerm("test");
			result.current.setIsSearchOpen(true);
			result.current.handleSearchMatchesUpdate([{ page: 1, wordIndex: 1 }]);
		});

		act(() => {
			result.current.handleCloseSearch();
		});

		expect(result.current.isSearchOpen).toBe(false);
		expect(result.current.searchTerm).toBe("");
		expect(result.current.searchMatches).toEqual([]);
		expect(result.current.currentMatchIndex).toBe(0);
	});

	it("opens search on Ctrl+F / Cmd+F if document exists", () => {
		const { result } = renderHook(() => useSearchState(true));

		// Mock keyboard event
		const event = new KeyboardEvent("keydown", {
			ctrlKey: true,
			key: "f",
			bubbles: true,
		});

		act(() => {
			window.dispatchEvent(event);
		});

		expect(result.current.isSearchOpen).toBe(true);
	});

	it("ignores Ctrl+F if no document exists", () => {
		const { result } = renderHook(() => useSearchState(false));

		const event = new KeyboardEvent("keydown", {
			ctrlKey: true,
			key: "f",
			bubbles: true,
		});

		act(() => {
			window.dispatchEvent(event);
		});

		expect(result.current.isSearchOpen).toBe(false);
	});

	it("closes search on Escape", () => {
		const { result } = renderHook(() => useSearchState(true));

		act(() => {
			result.current.setIsSearchOpen(true);
		});

		const event = new KeyboardEvent("keydown", {
			key: "Escape",
			bubbles: true,
		});

		act(() => {
			window.dispatchEvent(event);
		});

		expect(result.current.isSearchOpen).toBe(false);
	});
});

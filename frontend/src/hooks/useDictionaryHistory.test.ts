import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { APP_EVENTS } from "@/lib/events";
import { useDictionaryHistory } from "./useDictionaryHistory";

// Mock the dependencies
vi.mock("@/lib/auth", () => ({
	buildAuthHeaders: vi.fn(() => ({ Authorization: "Bearer test-token" })),
}));

vi.mock("@/lib/logger", () => ({
	createLogger: () => ({
		info: vi.fn(),
		error: vi.fn(),
	}),
}));

describe("useDictionaryHistory Hook", () => {
	const defaultProps = {
		sessionId: "test-session",
		paperId: "test-paper",
		token: "test-token",
	};

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
	});

	it("fetches saved notes on mount", async () => {
		const mockNotes = {
			notes: [{ note_id: "1", term: "hello", note: "こんにちは" }],
		};

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => mockNotes,
		});

		const { result } = renderHook(() => useDictionaryHistory(defaultProps));

		await waitFor(() => {
			expect(result.current.savedNotes).toHaveLength(1);
			expect(result.current.savedNotes[0].term).toBe("hello");
			expect(result.current.savedItems.has("hello")).toBe(true);
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/note/test-session"),
			expect.any(Object),
		);
	});

	it("refetches notes when APP_EVENTS.NOTES_UPDATED is dispatched", async () => {
		const mockNotes1 = {
			notes: [{ note_id: "1", term: "hello", note: "こんにちは" }],
		};
		const mockNotes2 = {
			notes: [
				{ note_id: "1", term: "hello", note: "こんにちは" },
				{ note_id: "2", term: "world", note: "世界" },
			],
		};

		(global.fetch as any)
			.mockResolvedValueOnce({ ok: true, json: async () => mockNotes1 })
			.mockResolvedValueOnce({ ok: true, json: async () => mockNotes2 });

		renderHook(() => useDictionaryHistory(defaultProps));

		await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

		act(() => {
			window.dispatchEvent(new Event(APP_EVENTS.NOTES_UPDATED));
		});

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledTimes(2);
		});
	});

	it("saves a new note and dispatches event", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({ status: "ok" }),
		});

		const dispatchSpy = vi.spyOn(window, "dispatchEvent");
		const { result } = renderHook(() => useDictionaryHistory(defaultProps));

		const newEntry = {
			word: "new",
			translation: "新しい",
		};

		await act(async () => {
			await result.current.handleSaveToNote(newEntry);
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/note"),
			expect.objectContaining({
				method: "POST",
				body: expect.stringContaining('"term":"new"'),
			}),
		);

		expect(result.current.savedItems.has("new")).toBe(true);
		expect(dispatchSpy).toHaveBeenCalledWith(expect.any(Event));
		expect(
			dispatchSpy.mock.calls.some(
				(call) => call[0].type === APP_EVENTS.NOTES_UPDATED,
			),
		).toBe(true);
	});
});

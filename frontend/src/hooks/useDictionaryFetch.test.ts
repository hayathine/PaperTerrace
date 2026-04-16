import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useDictionaryFetch } from "./useDictionaryFetch";

// Mock dependencies
vi.mock("@/config", () => ({
	API_URL: "http://localhost:8000",
}));

vi.mock("@/lib/auth", () => ({
	buildAuthHeaders: vi.fn(() => ({ Authorization: "Bearer test-token" })),
}));

vi.mock("@/lib/logger", () => ({
	createLogger: () => ({
		info: vi.fn(),
		warn: vi.fn(),
		error: vi.fn(),
		debug: vi.fn(),
	}),
}));

vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "ja" },
	}),
}));

describe("useDictionaryFetch Hook", () => {
	const defaultDeps = {
		term: "test-word",
		sessionId: "test-session",
		paperId: "test-paper",
		context: "some context text",
		conf: 0.9,
		imageUrl: undefined,
		currentSubTab: "translation" as const,
		token: "test-token",
		paperTitleRef: { current: "Test Paper Title" },
	};

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
	});

	it("should fetch word translation on mount", async () => {
		const mockResponse = {
			word: "test-word",
			translation: "テスト単語",
			source: "Gemini",
		};

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			headers: new Map([["content-type", "application/json"]]),
			json: async () => mockResponse,
		});

		const { result } = renderHook(() => useDictionaryFetch(defaultDeps));

		// Initially should show analyzing
		expect(result.current.loading).toBe(true);
		expect(result.current.entries[0]).toMatchObject({
			word: "test-word",
			translation: "...",
			is_analyzing: true,
		});

		await waitFor(() => {
			expect(result.current.loading).toBe(false);
			expect(result.current.entries[0]).toEqual(mockResponse);
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/translate/test-word"),
			expect.any(Object),
		);
	});

	it("should fetch from image URL if provided", async () => {
		const deps = { ...defaultDeps, imageUrl: "http://example.com/image.jpg" };
		const mockResponse = {
			word: "test-word",
			translation: "image explanation",
			source: "Gemini (Image)",
		};

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			headers: new Map([["content-type", "application/json"]]),
			json: async () => mockResponse,
		});

		const { result } = renderHook(() => useDictionaryFetch(deps));

		await waitFor(() => {
			expect(result.current.loading).toBe(false);
			expect(result.current.entries[0]).toEqual(mockResponse);
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/explain/image"),
			expect.objectContaining({
				method: "POST",
				body: expect.stringContaining(
					'"image_url":"http://example.com/image.jpg"',
				),
			}),
		);
	});

	it("should handle context explanation when currentSubTab is 'explanation'", async () => {
		const deps = { ...defaultDeps, currentSubTab: "explanation" as const };
		const mockResponse = {
			word: "test-word",
			translation: "detailed explanation",
			source: "Gemini (Context)",
		};

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			headers: new Map([["content-type", "application/json"]]),
			json: async () => mockResponse,
		});

		const { result } = renderHook(() => useDictionaryFetch(deps));

		await waitFor(() => {
			expect(result.current.explanationEntries[0]).toEqual(mockResponse);
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/explain/context"),
			expect.objectContaining({
				method: "POST",
				body: expect.stringContaining('"context":"some context text"'),
			}),
		);
	});

	it("should handle truncation for very long terms", async () => {
		const longTerm = "a".repeat(2100);
		const deps = { ...defaultDeps, term: longTerm };

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			headers: new Map([["content-type", "application/json"]]),
			json: async () => ({
				word: `${longTerm.slice(0, 2000)}…`,
				translation: "too long",
			}),
		});

		const { result } = renderHook(() => useDictionaryFetch(deps));

		await waitFor(() => {
			expect(result.current.isTruncated).toBe(true);
		});
	});

	it("should trigger deep translate callback", async () => {
		const onSubTabChange = vi.fn();
		const deps = { ...defaultDeps, onSubTabChange };

		const mockResponse = {
			word: "test-word",
			translation: "Deep Translation Result",
			source: "Gemini (Deep)",
		};

		(global.fetch as any).mockResolvedValue({
			ok: true,
			headers: new Map([["content-type", "application/json"]]),
			json: async () => mockResponse,
		});

		const { result } = renderHook(() => useDictionaryFetch(deps));

		await waitFor(() => expect(result.current.loading).toBe(false));

		const initialEntry = result.current.entries[0];

		await act(async () => {
			await result.current.handleDeepTranslate(initialEntry);
		});

		expect(onSubTabChange).toHaveBeenCalledWith("explanation");
		expect(result.current.explanationEntries[0]).toMatchObject({
			word: "test-word",
			translation: "Deep Translation Result",
			is_analyzing: false,
		});
	});

	it("should handle fetch errors gracefully", async () => {
		(global.fetch as any).mockRejectedValueOnce(new Error("Network Error"));

		const { result } = renderHook(() => useDictionaryFetch(defaultDeps));

		await waitFor(() => {
			expect(result.current.loading).toBe(false);
			expect(result.current.error).toBe("viewer.dictionary.error_unavailable");
		});
	});
});

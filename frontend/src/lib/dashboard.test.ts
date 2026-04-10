import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	fetchUserPapers,
	fetchUserStats,
	fetchUserTranslations,
} from "./dashboard";

describe("dashboard lib", () => {
	beforeEach(() => {
		vi.stubGlobal("fetch", vi.fn());
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe("fetchUserStats", () => {
		it("should fetch user stats with auth headers", async () => {
			const mockStats = {
				paper_count: 5,
				public_paper_count: 2,
				total_views: 10,
				total_likes: 3,
				note_count: 8,
				translation_count: 15,
				chat_count: 12,
			};

			(fetch as any).mockResolvedValue({
				ok: true,
				json: async () => mockStats,
			});

			const result = await fetchUserStats("test-token");

			expect(fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/auth/me/stats"),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: "Bearer test-token",
					}),
				}),
			);
			expect(result).toEqual(mockStats);
		});

		it("should throw error if fetch fails", async () => {
			(fetch as any).mockResolvedValue({
				ok: false,
			});

			await expect(fetchUserStats("test-token")).rejects.toThrow(
				"Failed to fetch user stats",
			);
		});
	});

	describe("fetchUserTranslations", () => {
		it("should fetch user translations with pagination", async () => {
			const mockResponse = {
				translations: [],
				total: 0,
				page: 1,
				per_page: 20,
			};

			(fetch as any).mockResolvedValue({
				ok: true,
				json: async () => mockResponse,
			});

			const result = await fetchUserTranslations("test-token", 2, 50);

			expect(fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/auth/me/translations?page=2&per_page=50"),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: "Bearer test-token",
					}),
				}),
			);
			expect(result).toEqual(mockResponse);
		});

		it("should throw error if fetch fails", async () => {
			(fetch as any).mockResolvedValue({
				ok: false,
			});

			await expect(fetchUserTranslations("test-token")).rejects.toThrow(
				"Failed to fetch translations",
			);
		});
	});

	describe("fetchUserPapers", () => {
		it("should fetch user papers with limit", async () => {
			const mockResponse = { papers: [] };

			(fetch as any).mockResolvedValue({
				ok: true,
				json: async () => mockResponse,
			});

			const result = await fetchUserPapers("test-token", 5);

			expect(fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/papers?limit=5"),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: "Bearer test-token",
					}),
				}),
			);
			expect(result).toEqual(mockResponse);
		});

		it("should throw error if fetch fails", async () => {
			(fetch as any).mockResolvedValue({
				ok: false,
			});

			await expect(fetchUserPapers("test-token")).rejects.toThrow(
				"Failed to fetch papers",
			);
		});
	});
});

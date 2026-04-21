import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	generateRecommendations,
	submitRecommendationRollout,
	syncTrajectory,
} from "./recommendation";

describe("recommendation lib", () => {
	beforeEach(() => {
		vi.stubGlobal("fetch", vi.fn());
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe("syncTrajectory", () => {
		it("should call fetch with correct headers and payload", async () => {
			const payload = { session_id: "s1", paper_id: "p1" };
			const token = "test-token";

			(fetch as any).mockResolvedValue({ ok: true });

			await syncTrajectory(payload, token);

			expect(fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/recommendation/sync"),
				expect.objectContaining({
					method: "POST",
					headers: expect.objectContaining({
						Authorization: "Bearer test-token",
						"Content-Type": "application/json",
					}),
					body: JSON.stringify(payload),
				}),
			);
		});

		it("should not include Authorization header if token is null", async () => {
			(fetch as any).mockResolvedValue({ ok: true });
			await syncTrajectory({ session_id: "s1" }, null);

			const lastCall = (fetch as any).mock.calls[0];
			expect(lastCall[1].headers.Authorization).toBeUndefined();
		});
	});

	describe("submitRecommendationRollout", () => {
		it("should throw error if response is not ok", async () => {
			(fetch as any).mockResolvedValue({
				ok: false,
				status: 500,
				text: async () => "External Error",
			});

			await expect(
				submitRecommendationRollout(
					{ session_id: "s1", user_score: 5 },
					"token",
				),
			).rejects.toThrow("Failed to submit rollout (500): External Error");
		});

		it("should return json on success", async () => {
			(fetch as any).mockResolvedValue({
				ok: true,
				json: async () => ({ status: "ok" }),
			});

			const result = await submitRecommendationRollout(
				{ session_id: "s1", user_score: 5 },
				"token",
			);
			expect(result).toEqual({ status: "ok" });
		});
	});

	describe("submitRecommendationRollout", () => {
		it("should throw error if response is not ok", async () => {
			(fetch as any).mockResolvedValue({
				ok: false,
				status: 500,
				text: async () => "External Error",
			});

			await expect(
				submitRecommendationRollout(
					{ session_id: "s1", user_score: 5 },
					"token",
				),
			).rejects.toThrow("Failed to submit rollout (500): External Error");
		});

		it("should return json on success", async () => {
			(fetch as any).mockResolvedValue({
				ok: true,
				json: async () => ({ status: "ok" }),
			});

			const result = await submitRecommendationRollout(
				{ session_id: "s1", user_score: 5 },
				"token",
			);
			expect(result).toEqual({ status: "ok" });
		});
	});

	describe("generateRecommendations", () => {
		it("should call energy/generate endpoint", async () => {
			(fetch as any).mockResolvedValue({
				ok: true,
				json: async () => ({ recommendations: [] }),
			});

			await generateRecommendations("session-id", "token");

			expect(fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/recommendation/generate"),
				expect.objectContaining({
					body: JSON.stringify({ session_id: "session-id" }),
				}),
			);
		});
	});
});

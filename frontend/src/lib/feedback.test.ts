import { beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL } from "@/config";
import { type FeedbackPayload, submitFeedback } from "./feedback";

// Global fetch mock
const globalFetch = vi.fn();
vi.stubGlobal("fetch", globalFetch);

describe("feedback lib", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("submits feedback successfully", async () => {
		const payload: FeedbackPayload = {
			session_id: "sess-123",
			target_type: "chat",
			user_score: 1,
			user_comment: "Good job!",
		};

		globalFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => ({ status: "ok" }),
		});

		const result = await submitFeedback(payload);

		expect(globalFetch).toHaveBeenCalledWith(`${API_URL}/api/feedback`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});
		expect(result).toEqual({ status: "ok" });
	});

	it("throws error if feedback submission fails", async () => {
		const payload: FeedbackPayload = {
			session_id: "sess-123",
			target_type: "summary",
		};

		globalFetch.mockResolvedValueOnce({
			ok: false,
		});

		await expect(submitFeedback(payload)).rejects.toThrow(
			"Feedback submission failed",
		);
	});

	it("throws error if fetch fails", async () => {
		const payload: FeedbackPayload = {
			session_id: "sess-123",
			target_type: "translation",
		};

		globalFetch.mockRejectedValueOnce(new Error("Network Error"));

		await expect(submitFeedback(payload)).rejects.toThrow("Network Error");
	});
});

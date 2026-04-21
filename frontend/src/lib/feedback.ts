import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("FeedbackLib");

export interface FeedbackPayload {
	session_id: string;
	target_type:
		| "recommendation"
		| "summary"
		| "critique"
		| "related_papers"
		| "chat"
		| "translation"
		| "figure_insight";
	target_id?: string;
	trace_id?: string;
	user_rating?: number; // 1 for Good, 0 for Bad (binary feedback)
	user_comment?: string;
}

export async function submitFeedback(payload: FeedbackPayload) {
	try {
		const response = await fetch(`${API_URL}/api/feedback`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});
		if (!response.ok) throw new Error("Feedback submission failed");
		return response.json();
	} catch (error) {
		log.error("submit_feedback", "Failed to submit feedback", { error });

		throw error;
	}
}

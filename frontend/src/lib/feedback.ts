import { API_URL } from "@/config";

export interface FeedbackPayload {
	session_id: string;
	target_type:
		| "recommendation"
		| "summary"
		| "critique"
		| "related_papers"
		| "chat"
		| "translation";
	target_id?: string;
	user_score?: number; // 1 for Good, 0 for Bad
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
		console.error("Failed to submit feedback:", error);
		throw error;
	}
}

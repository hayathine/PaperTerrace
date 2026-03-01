import { API_URL } from "@/config";

export interface WordClickEvent {
	word: string;
	context: string;
	section: string;
	timestamp: number;
}

export interface RecommendationSyncPayload {
	session_id: string;
	paper_id?: string;
	paper_title?: string;
	paper_abstract?: string;
	paper_keywords?: string[];
	paper_difficulty?: string;
	conversation_history?: string;
	word_clicks?: WordClickEvent[];
	session_duration?: number;
}

export interface RecommendationFeedbackPayload {
	session_id: string;
	user_score: number;
	user_comment?: string;
	clicked_paper?: string;
	followed_up_query?: boolean;
}

export interface RecommendedPaper {
	title: string;
	abstract: string;
	url?: string;
	authors?: { name: string }[];
	year?: number;
	openAccessPdf?: { url: string };
	citationCount?: number;
}

export interface RecommendationGenerateResponse {
	recommendations: RecommendedPaper[];
	reasoning: string;
	knowledge_level: string;
	search_queries: string[];
}

/**
 * Synchronize trajectory data with backend
 */
export async function syncTrajectory(payload: RecommendationSyncPayload) {
	try {
		// Send asynchronously without blocking main thread
		fetch(`${API_URL}/api/recommendation/sync`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
			keepalive: true,
		}).catch((err) => console.error("Failed to sync trajectory", err));
	} catch (error) {
		console.error("Sync error", error);
	}
}

/**
 * Submit feedback for recommendations
 */
export async function submitRecommendationFeedback(
	payload: RecommendationFeedbackPayload,
) {
	const res = await fetch(`${API_URL}/api/recommendation/feedback`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload),
	});
	if (!res.ok) {
		throw new Error("Failed to submit feedback");
	}
	return res.json();
}

/**
 * Generate personal paper recommendations
 */
export async function generateRecommendations(
	sessionId: string,
): Promise<RecommendationGenerateResponse> {
	const res = await fetch(`${API_URL}/api/recommendation/generate`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ session_id: sessionId }),
	});
	if (!res.ok) {
		throw new Error("Failed to generate recommendations");
	}
	return res.json();
}

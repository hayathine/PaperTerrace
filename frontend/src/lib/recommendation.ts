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
 * Build common headers for recommendation API requests.
 */
function buildHeaders(token: string | null): Record<string, string> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
	};
	if (token) {
		headers.Authorization = `Bearer ${token}`;
	}
	return headers;
}

/**
 * Synchronize trajectory data with backend.
 * Fire-and-forget but errors are logged with details.
 */
export async function syncTrajectory(
	payload: RecommendationSyncPayload,
	token: string | null,
) {
	try {
		fetch(`${API_URL}/api/recommendation/sync`, {
			method: "POST",
			headers: buildHeaders(token),
			body: JSON.stringify(payload),
			keepalive: true,
		}).catch((err) => console.error("Failed to sync trajectory:", err));
	} catch (error) {
		console.error("Sync error:", error);
	}
}

/**
 * Submit feedback for recommendations.
 */
export async function submitRecommendationFeedback(
	payload: RecommendationFeedbackPayload,
	token: string | null,
) {
	const res = await fetch(`${API_URL}/api/recommendation/feedback`, {
		method: "POST",
		headers: buildHeaders(token),
		body: JSON.stringify(payload),
	});
	if (!res.ok) {
		const detail = await res.text().catch(() => "");
		throw new Error(`Failed to submit feedback (${res.status}): ${detail}`);
	}
	return res.json();
}

/**
 * Generate personal paper recommendations.
 */
export async function generateRecommendations(
	sessionId: string,
	token: string | null,
): Promise<RecommendationGenerateResponse> {
	const res = await fetch(`${API_URL}/api/recommendation/generate`, {
		method: "POST",
		headers: buildHeaders(token),
		body: JSON.stringify({ session_id: sessionId }),
	});
	if (!res.ok) {
		const detail = await res.text().catch(() => "");
		throw new Error(
			`Failed to generate recommendations (${res.status}): ${detail}`,
		);
	}
	return res.json();
}

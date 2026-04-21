import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";

export interface UserStats {
	paper_count: number;
	public_paper_count: number;
	total_views: number;
	total_likes: number;
	note_count: number;
	translation_count: number;
	chat_count: number;
}

export interface TranslationEntry {
	term: string;
	note: string;
	paper_id: string | null;
	page_number: number | null;
	created_at: string;
}

export interface TranslationsResponse {
	translations: TranslationEntry[];
	total: number;
	page: number;
	per_page: number;
}

export async function fetchUserStats(token: string): Promise<UserStats> {
	const res = await fetch(`${API_URL}/api/auth/me/stats`, {
		headers: buildAuthHeaders(token),
	});
	if (!res.ok) throw new Error("Failed to fetch user stats");
	return res.json();
}

export async function fetchUserTranslations(
	token: string,
	page = 1,
	perPage = 20,
): Promise<TranslationsResponse> {
	const res = await fetch(
		`${API_URL}/api/auth/me/translations?page=${page}&per_page=${perPage}`,
		{ headers: buildAuthHeaders(token) },
	);
	if (!res.ok) throw new Error("Failed to fetch translations");
	return res.json();
}

export interface PaperEntry {
	paper_id: string;
	title: string | null;
	created_at: string;
	tags?: string[];
}

export async function fetchUserPapers(
	token: string,
	limit = 10,
): Promise<{ papers: PaperEntry[] }> {
	const res = await fetch(`${API_URL}/api/papers?limit=${limit}`, {
		headers: buildAuthHeaders(token),
	});
	if (!res.ok) throw new Error("Failed to fetch papers");
	return res.json();
}

export interface UserPersona {
	knowledge_level: string | null;
	interests: string[] | null;
	unknown_concepts: string[] | null;
	preferred_direction: string | null;
	updated_at: string | null;
}

export async function fetchUserPersona(
	token: string,
): Promise<UserPersona | null> {
	const res = await fetch(`${API_URL}/api/auth/me/persona`, {
		headers: buildAuthHeaders(token),
	});
	if (!res.ok) return null;
	const data = await res.json();
	if (!data || Object.keys(data).length === 0) return null;
	return data as UserPersona;
}

export async function deletePaper(
	token: string,
	paperId: string,
): Promise<void> {
	const res = await fetch(`${API_URL}/api/papers/${paperId}`, {
		method: "DELETE",
		headers: buildAuthHeaders(token),
	});
	if (!res.ok) throw new Error("Failed to delete paper");
}

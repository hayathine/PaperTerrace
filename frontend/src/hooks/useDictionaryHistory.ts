import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";
import { APP_EVENTS } from "@/lib/events";
import { createLogger } from "@/lib/logger";

const log = createLogger("useDictionaryHistory");

export interface SavedNote {
	note_id: string;
	term: string;
	note: string;
	page_number?: number;
	created_at?: string;
}

interface UseDictionaryHistoryDeps {
	sessionId: string;
	paperId: string | null | undefined;
	token: string | null;
}

export function useDictionaryHistory({
	sessionId,
	paperId,
	token,
}: UseDictionaryHistoryDeps) {
	const [savedNotes, setSavedNotes] = useState<SavedNote[]>([]);
	const [savedItems, setSavedItems] = useState<Set<string>>(new Set());

	// paperId 変化時のリセット（null → 実IDへの遷移はスキップ）
	const prevPaperIdRef = useRef<string | null | undefined>(paperId);
	useEffect(() => {
		if (
			prevPaperIdRef.current !== undefined &&
			paperId !== prevPaperIdRef.current
		) {
			const isProcessingFinished =
				prevPaperIdRef.current === null && paperId !== null;
			if (!isProcessingFinished) {
				setSavedItems(new Set());
			}
		}
		prevPaperIdRef.current = paperId;
	}, [paperId]);

	const fetchSavedNotes = useCallback(async () => {
		try {
			const headers = buildAuthHeaders(token);
			const baseUrl = API_URL || window.location.origin;
			const url = new URL(`/api/note/${sessionId}`, baseUrl);
			if (paperId) url.searchParams.append("paper_id", paperId);

			const res = await fetch(url.toString(), { headers });
			if (res.ok) {
				const data = await res.json();
				if (data.notes) {
					const terms = data.notes.map((n: { term: string }) => n.term);
					setSavedItems(new Set(terms));
					setSavedNotes(data.notes.filter((n: { term: string }) => n.term));
				}
			}
		} catch (e) {
			log.error("fetch_saved_notes", "fetchSavedNotes error", { error: e });
		}
	}, [sessionId, paperId, token]);

	useEffect(() => {
		if (sessionId && paperId) fetchSavedNotes();

		const handleNotesUpdated = () => {
			if (sessionId && paperId) fetchSavedNotes();
		};
		window.addEventListener(APP_EVENTS.NOTES_UPDATED, handleNotesUpdated);
		return () => {
			window.removeEventListener(APP_EVENTS.NOTES_UPDATED, handleNotesUpdated);
		};
	}, [sessionId, paperId, fetchSavedNotes]);

	const handleSaveToNote = useCallback(
		async (
			entry: {
				word: string;
				translation: string;
				coords?: { page: number; x: number; y: number };
			},
			fallbackCoords?: { page: number; x: number; y: number },
		) => {
			const targetCoords = entry.coords || fallbackCoords;
			try {
				const headers = buildAuthHeaders(token, {
					"Content-Type": "application/json",
				});
				const res = await fetch(`${API_URL}/api/note`, {
					method: "POST",
					headers,
					body: JSON.stringify({
						session_id: sessionId,
						paper_id: paperId,
						term: entry.word,
						note: entry.translation,
						page_number: targetCoords?.page,
						x: targetCoords?.x,
						y: targetCoords?.y,
					}),
				});
				if (res.ok) {
					setSavedItems((prev) => new Set(prev).add(entry.word));
					window.dispatchEvent(new Event(APP_EVENTS.NOTES_UPDATED));
				}
			} catch (e) {
				log.error("save_to_note", "Failed to save note", {
					error: e,
					term: entry.word,
				});
			}
		},
		[sessionId, paperId, token],
	);

	return { savedNotes, savedItems, handleSaveToNote };
}

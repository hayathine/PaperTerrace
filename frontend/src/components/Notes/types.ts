export interface Note {
	note_id: string;
	session_id: string;
	term: string;
	note: string;
	image_url?: string;
	page_number?: number;
	x?: number;
	y?: number;
	created_at?: string;
}

export interface NoteRequest {
	session_id: string;
	term: string;
	note: string;
	image_url?: string;
	page_number?: number;
	x?: number;
	y?: number;
}

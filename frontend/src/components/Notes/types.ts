export interface Note {
    note_id: string;
    session_id: string;
    term: string;
    note: string;
    image_url?: string;
    created_at?: string;
}

export interface NoteRequest {
    session_id: string;
    term: string;
    note: string;
    image_url?: string;
}

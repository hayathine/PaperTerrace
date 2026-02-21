import Dexie, { type Table } from "dexie";

export interface PaperCache {
	id: string; // paper_id
	file_hash: string;
	title: string;
	author?: string;
	ocr_text?: string;
	layout_json?: string;
	abstract?: string;
	full_summary?: string;
	section_summary_json?: string;
	html_content?: string;
	last_accessed: number;
}

export interface ImageCache {
	id: string; // image_url or unique key
	paper_id: string;
	blob: Blob;
	label: "figure" | "table" | "page" | "formula";
	page_number?: number;
	bbox?: number[];
	created_at: number;
}

export interface EditHistory {
	id?: number;
	paper_id: string;
	type: "note" | "stamp";
	data: any;
	synced: boolean;
	created_at: number;
}

export class PaperTerraceDB extends Dexie {
	papers!: Table<PaperCache>;
	images!: Table<ImageCache>;
	edit_history!: Table<EditHistory>;

	constructor() {
		super("PaperTerraceDB");
		this.version(2).stores({
			papers: "id, last_accessed, file_hash",
			images: "id, paper_id, label",
			edit_history: "++id, paper_id, synced",
		});
	}
}

export const db = new PaperTerraceDB();

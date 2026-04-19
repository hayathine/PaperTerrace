import Dexie, { type Table } from "dexie";
import { createLogger } from "@/lib/logger";

const log = createLogger("DB");

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
	server_updated_at?: number;
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

export interface Bookmark {
	id?: number; // auto-increment
	paper_id: string;
	paper_title: string;
	page_number: number;
	created_at: number;
}

export class PaperTerraceDB extends Dexie {
	papers!: Table<PaperCache>;
	images!: Table<ImageCache>;
	edit_history!: Table<EditHistory>;
	bookmarks!: Table<Bookmark>;

	constructor() {
		super("PaperTerraceDB");
		this.version(2).stores({
			papers: "id, last_accessed, file_hash",
			images: "id, paper_id, label",
			edit_history: "++id, paper_id, synced",
		});
		this.version(3).stores({
			papers: "id, last_accessed, file_hash",
			images: "id, paper_id, label",
			edit_history: "++id, paper_id, synced",
			bookmarks: "++id, paper_id, page_number, created_at",
		});
	}
}

export const db = new PaperTerraceDB();

/** Whether IndexedDB is available and initialized. */
let dbAvailable = true;

/**
 * Open the database and verify IndexedDB works.
 * Call this once at app startup; all db helpers should check `isDbAvailable()`
 * before performing operations.
 */
export async function initDB(): Promise<boolean> {
	try {
		await db.open();
		dbAvailable = true;
	} catch (e) {
		log.warn("init_db", "IndexedDB unavailable — caching disabled", {
			error: e,
		});

		dbAvailable = false;
	}
	return dbAvailable;
}

export function isDbAvailable(): boolean {
	return dbAvailable;
}

/**
 * Maximum total cache size (bytes). When exceeded, oldest papers are evicted.
 * 500 MB — generous for typical usage while preventing runaway growth.
 */
const MAX_CACHE_BYTES = 500 * 1024 * 1024;

/**
 * Evict the oldest cached papers until total storage is below the limit.
 * Silently returns if IndexedDB or the Storage API is unavailable.
 */
export async function evictIfOverQuota(): Promise<void> {
	if (!dbAvailable) return;
	try {
		const estimate =
			navigator.storage?.estimate && (await navigator.storage.estimate());
		if (!estimate?.usage || estimate.usage < MAX_CACHE_BYTES) return;

		// Delete images then papers, oldest first
		const oldest = await db.papers.orderBy("last_accessed").limit(5).toArray();
		for (const p of oldest) {
			await db.images.where("paper_id").equals(p.id).delete();
			await db.papers.delete(p.id);
		}
	} catch (e) {
		log.warn("evict_cache", "Cache eviction failed", { error: e });
	}
}

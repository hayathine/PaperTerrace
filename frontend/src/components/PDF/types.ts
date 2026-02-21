export interface WordBox {
	text: string;
	bbox: [number, number, number, number]; // [x, y, w, h] or [x1, y1, x2, y2]
}

export interface PageData {
	page_num: number;
	image_url: string;
	width: number;
	height: number;
	words: PageWord[];
	figures?: Figure[];
	links?: Link[];
	content?: string;
}

export interface Link {
	url: string;
	bbox: number[]; // [x1, y1, x2, y2]
}

export interface PageWord {
	word: string;
	bbox: number[]; // [x1, y1, x2, y2]
}

export interface Figure {
	bbox: [number, number, number, number]; // [x1, y1, x2, y2]
	image_url: string;
	page_num: number;
	label?: string; // 'figure', 'table', 'equation'
	explanation?: string;
	latex?: string;
}

export interface LineData {
	words: PageWord[];
	bbox: number[];
}

export interface PageWithLines extends PageData {
	lines: LineData[];
}

export interface ViewerState {
	pages: PageData[];
	isLoading: boolean;
	error: string | null;
	paperId: string | null;
}

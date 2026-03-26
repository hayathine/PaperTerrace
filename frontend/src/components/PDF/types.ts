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
	conf?: number;
}

export interface Figure {
	id?: string;
	bbox: [number, number, number, number]; // [x1, y1, x2, y2]
	image_url?: string | null; // クロップ画像URLがない場合は null
	page_num: number;
	label?: string; // 'figure', 'table', 'equation'
	caption?: string;
	explanation?: string;
	latex?: string;
	conf?: number;
}

/** ClickModeで図をクリックした際にFigureInsightパネルへ渡すデータ */
export interface SelectedFigure {
	id?: string;
	image_url?: string | null; // クロップ画像URLがない場合は null
	label?: string;
	caption?: string;
	page_number: number;
	conf?: number;
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

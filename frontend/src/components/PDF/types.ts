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
    figures?: FigureData[];
    links?: LinkData[];
}

export interface FigureData {
    bbox: number[]; // [x1, y1, x2, y2]
    label: string;
    image_url?: string;
    latex?: string;
}

export interface LinkData {
    bbox: number[]; // [x1, y1, x2, y2]
    url: string;
}

export interface PageWord {
    word: string;
    bbox: number[]; // [x1, y1, x2, y2]
}

export interface ViewerState {
    pages: PageData[];
    isLoading: boolean;
    error: string | null;
    paperId: string | null;
}

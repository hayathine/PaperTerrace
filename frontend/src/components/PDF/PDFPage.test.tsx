import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PDFPage from "./PDFPage";
import type { PageData } from "./types";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "en" },
	}),
}));

// Mock dexie
vi.mock("dexie-react-hooks", () => ({
	useLiveQuery: () => [],
}));
vi.mock("@/db", () => ({
	db: {
		images: { get: vi.fn() },
	},
}));

// Mock IntersectionObserver
vi.mock("../../hooks/useIntersectionObserver", () => ({
	useIntersectionObserver: () => true,
}));

const mockPage: PageData = {
	page_num: 1,
	image_url: "http://example.com/page1.jpg",
	width: 612,
	height: 792,
	content: "Hello World",
	words: [
		{ word: "Hello", bbox: [100, 100, 150, 120], conf: 0.99 },
		{ word: "World", bbox: [160, 100, 210, 120], conf: 0.99 },
	],
	links: [],
	figures: [],
};

describe("PDFPage Component", () => {
	it("renders page image", () => {
		render(
			<div className="group/viewer" data-click-mode="viewer">
				<PDFPage page={mockPage} />
			</div>,
		);
		const img = screen.getByAltText("Page 1");
		expect(img).toBeInTheDocument();
		expect(img).toHaveAttribute("src", mockPage.image_url);
	});

	it("triggers onWordClick when a word is clicked", () => {
		const onWordClick = vi.fn();
		render(
			<div className="group/viewer" data-click-mode="viewer">
				<PDFPage page={mockPage} onWordClick={onWordClick} />
			</div>,
		);

		// Find the word 'Hello' - using findByTitle since it has title=w.word
		const wordEl = screen.getByTitle("Hello");
		fireEvent.click(wordEl);

		expect(onWordClick).toHaveBeenCalledWith(
			"Hello",
			expect.any(String),
			expect.objectContaining({ page: 1 }),
			0.99,
		);
	});

	it("highlights search terms", () => {
		render(
			<div className="group/viewer" data-click-mode="viewer">
				<PDFPage page={mockPage} searchTerm="Hello" />
			</div>,
		);
		const wordEl = screen.getByTitle("Hello");
		// We check the classes applied for search match
		expect(wordEl.className).toContain("bg-amber-300/50");
	});
});

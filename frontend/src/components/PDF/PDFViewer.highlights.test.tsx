import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PDFViewer from "./PDFViewer";

// Mock dependencies
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "en" },
	}),
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
		getToken: () => Promise.resolve("test-token"),
		isGuest: false,
	}),
}));

const mockPaperCache = {
	getCachedPaper: vi.fn(),
	savePaperToCache: vi.fn().mockResolvedValue(undefined),
	cachePaperImages: vi.fn().mockResolvedValue(undefined),
	deleteCorruptedCache: vi.fn(),
};
vi.mock("../../db/hooks", () => ({
	usePaperCache: () => mockPaperCache,
	useBookmarks: () => ({
		addBookmark: vi.fn(),
		getBookmarks: vi.fn(() => Promise.resolve([])),
		getPageBookmarks: vi.fn(() => Promise.resolve(false)),
		deleteBookmark: vi.fn(),
	}),
}));

vi.mock("../../db/index", () => ({
	isDbAvailable: () => true,
}));

vi.mock("@/lib/logger", () => ({
	createLogger: () => ({
		info: vi.fn(),
		error: vi.fn(),
		warn: vi.fn(),
		debug: vi.fn(),
	}),
}));

// Mock IntersectionObserver
const mockIntersectionObserver = vi.fn();
mockIntersectionObserver.mockReturnValue({
	observe: vi.fn(),
	unobserve: vi.fn(),
	disconnect: vi.fn(),
});
vi.stubGlobal("IntersectionObserver", mockIntersectionObserver);

// Mock PDFPage to verify evidenceHighlights prop
const MockPDFPage = ({ page, evidenceHighlights = [] }: any) => (
	<div data-testid={`pdf-page-${page.page_num}`}>
		Page {page.page_num}
		<div data-testid={`highlights-count-${page.page_num}`}>
			{evidenceHighlights.length}
		</div>
		{evidenceHighlights.map((h: any, i: number) => (
			<div
				key={i}
				data-testid={`highlight-${page.page_num}-${i}`}
				data-coords={JSON.stringify(h)}
			/>
		))}
	</div>
);

vi.mock("./PDFPage", () => ({
	default: (props: any) => <MockPDFPage {...props} />,
}));

describe("PDFViewer Grounds/Highlights Logic", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn().mockImplementation(async (url, options) => {
			const urlStr = typeof url === "string" ? url : (url as URL).toString();
			if (urlStr.includes("/api/papers/paper1/figures")) {
				return { ok: true, json: async () => ({ figures: [] }) };
			}
			if (options?.method === "HEAD") {
				return { ok: true };
			}
			if (urlStr.includes("/api/session-context")) {
				return { ok: true };
			}
			if (urlStr.includes("/api/papers/paper1")) {
				return {
					ok: true,
					json: async () => ({
						id: "paper1",
						file_hash: "hash123",
						layout_json: "[]",
						ocr_text: "[]",
					}),
				};
			}
			return { ok: true, json: async () => ({}) };
		});
	});

	it("correctly computes and passes highlights for evidence supports", async () => {
		const mockPages = [
			{
				page_num: 1,
				width: 1000,
				height: 1000,
				words: [
					{ word: "The", bbox: [100, 100, 150, 120] },
					{ word: "quick", bbox: [160, 100, 220, 120] },
					{ word: "brown", bbox: [230, 100, 300, 120] },
					{ word: "fox", bbox: [310, 100, 350, 120] },
				],
			},
		];

		const mockEvidence = {
			supports: [
				{
					segment_text: "quick brown fox",
				},
			],
		};

		mockPaperCache.getCachedPaper.mockResolvedValue({
			id: "paper1",
			file_hash: "hash123",
			layout_json: JSON.stringify(mockPages),
		});

		render(<PDFViewer paperId="paper1" evidence={mockEvidence} mode="text" />);

		await waitFor(() => {
			expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
		});

		// Check if highlights were passed to PDFPage
		// "quick brown fox" matches words[1], words[2], words[3]
		// x1=160, y1=100, x2=350, y2=120
		// normalized: x=0.16, y=0.1, width=0.19, height=0.02
		await waitFor(() => {
			const countEl = screen.getByTestId("highlights-count-1");
			expect(countEl.textContent).toBe("1");
		});

		const highlightEl = screen.getByTestId("highlight-1-0");
		const coords = JSON.parse(highlightEl.getAttribute("data-coords") || "{}");

		expect(coords.x).toBeCloseTo(0.16);
		expect(coords.y).toBeCloseTo(0.1);
		expect(coords.width).toBeCloseTo(0.19);
		expect(coords.height).toBeCloseTo(0.02);
	});
});

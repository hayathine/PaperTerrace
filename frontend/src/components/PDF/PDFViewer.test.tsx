import {
	act,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PDFViewer from "./PDFViewer";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "en" },
	}),
}));

// Mock AuthContext
vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
		isGuest: false,
	}),
}));

// Mock Paper Cache hook
const mockPaperCache = {
	getCachedPaper: vi.fn(),
	savePaperToCache: vi.fn().mockResolvedValue(undefined),
	cachePaperImages: vi.fn().mockResolvedValue(undefined),
	deleteCorruptedCache: vi.fn(),
};
vi.mock("../../db/hooks", () => ({
	usePaperCache: () => mockPaperCache,
}));

// Mock DB
vi.mock("../../db/index", () => ({
	isDbAvailable: () => true,
}));

// Mock logger
vi.mock("@/lib/logger", () => ({
	createLogger: () => ({
		info: vi.fn(),
		error: vi.fn(),
		warn: vi.fn(),
		debug: vi.fn(),
	}),
}));

// Mock components
vi.mock("./PDFPage", () => ({
	default: ({ page, onWordClick }: any) => (
		<div data-testid={`pdf-page-${page.page_num}`}>
			Page {page.page_num}
			<button
				type="button"
				onClick={() =>
					onWordClick?.("hello", "context", { page: 1, x: 10, y: 10 }, 0.99)
				}
				data-testid={`click-word-${page.page_num}`}
			>
				Click Word
			</button>
		</div>
	),
}));

vi.mock("./TextModeViewer", () => ({
	default: ({ pages }: any) => (
		<div data-testid="text-mode-viewer">Text Mode: {pages.length} pages</div>
	),
}));

// Mock SSE
class MockEventSource {
	onmessage: ((ev: any) => void) | null = null;
	onerror: ((ev: any) => void) | null = null;
	url: string;

	constructor(url: string) {
		this.url = url;
		// Trigger the constructor-based SSE setup if needed
	}

	close() {}

	// Helper to simulate receiving messages
	emitMessage(data: any) {
		if (this.onmessage) {
			this.onmessage({ data: JSON.stringify(data) });
		}
	}

	emitError(err: any) {
		if (this.onerror) {
			this.onerror(err);
		}
	}
}

describe("PDFViewer Component", () => {
	let mockES: MockEventSource;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn().mockImplementation(async (url) => {
			if (url.includes("/request-upload-url")) {
				return {
					ok: true,
					json: async () => ({ upload_url: null, already_cached: false }),
				};
			}
			return {
				ok: true,
				json: async () => ({ task_id: "test-task", stream_url: "/stream" }),
			};
		});

		mockES = new MockEventSource("/stream");
		(global as any).EventSource = vi.fn().mockImplementation((url) => {
			mockES.url = url;
			return mockES;
		});

		// Mock scrollTo
		window.HTMLElement.prototype.scrollTo = vi.fn();
		window.HTMLElement.prototype.scrollIntoView = vi.fn();
	});

	it("renders in idle state without props", () => {
		render(<PDFViewer />);
		// Initially it might be idle or attempting to start if no propPaperId
	});

	it("loads and displays existing paper from paperId", async () => {
		const mockPage = {
			page_num: 1,
			image_url: "page1.jpg",
			width: 100,
			height: 100,
			words: [],
		};

		mockPaperCache.getCachedPaper.mockResolvedValue({
			id: "test-paper",
			title: "Test Paper",
			file_hash: "fake-hash",
			ocr_text: JSON.stringify(["page1 content"]),
			layout_json: JSON.stringify([mockPage]),
		});

		render(<PDFViewer paperId="test-paper" mode="text" />);

		await waitFor(() => {
			expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
		});

		expect(mockPaperCache.getCachedPaper).toHaveBeenCalledWith("test-paper");
	});

	it("starts analysis when uploadFile is provided", async () => {
		const file = new File(["test data"], "test.pdf", {
			type: "application/pdf",
		});
		const onStatusChange = vi.fn();

		render(
			<PDFViewer
				uploadFile={file}
				onStatusChange={onStatusChange}
				mode="text"
			/>,
		);

		await waitFor(() => {
			const statuses = onStatusChange.mock.calls.map((c) => c[0]);
			expect(
				statuses.some((s) => s === "uploading" || s === "processing"),
			).toBe(true);
		});
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/analyze-pdf-json"),
			expect.anything(),
		);

		await waitFor(() => {
			expect(onStatusChange).toHaveBeenCalledWith("processing");
		});

		// Simulate receiving a page via SSE
		act(() => {
			mockES.emitMessage({
				type: "page",
				data: { page_num: 1, image_url: "p1.jpg", words: [] },
			});
		});

		await waitFor(() => {
			expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
		});

		// Simulate done
		act(() => {
			mockES.emitMessage({
				type: "done",
				paper_id: "new-paper-123",
			});
		});

		await waitFor(() => {
			expect(onStatusChange).toHaveBeenCalledWith("done");
		});
	});

	it("handles word clicks and forwards them to onWordClick prop", async () => {
		const mockPage = {
			page_num: 1,
			image_url: "p1.jpg",
			words: [],
		};
		mockPaperCache.getCachedPaper.mockResolvedValue({
			id: "test",
			file_hash: "fake-hash",
			layout_json: JSON.stringify([mockPage]),
		});

		const onWordClick = vi.fn();
		render(<PDFViewer paperId="test" onWordClick={onWordClick} mode="text" />);

		const wordButton = await screen.findByTestId("click-word-1");
		fireEvent.click(wordButton);

		expect(onWordClick).toHaveBeenCalledWith(
			"hello",
			expect.any(String),
			expect.objectContaining({ page: 1 }),
			0.99,
		);
	});

	it("switches between PDF grid and plaintext mode", async () => {
		const mockPage = {
			page_num: 1,
			image_url: "p1.jpg",
			words: [],
		};
		mockPaperCache.getCachedPaper.mockResolvedValue({
			id: "test",
			file_hash: "fake-hash",
			layout_json: JSON.stringify([mockPage]),
		});

		const { rerender } = render(<PDFViewer paperId="test" mode="text" />);

		await waitFor(() => {
			expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
		});

		rerender(<PDFViewer paperId="test" mode="plaintext" />);

		expect(screen.getByTestId("text-mode-viewer")).toBeInTheDocument();
	});

	it("handles SSE errors gracefully", async () => {
		vi.useFakeTimers();
		const file = new File(["test data"], "test.pdf", {
			type: "application/pdf",
		});
		const onStatusChange = vi.fn();

		render(
			<PDFViewer
				uploadFile={file}
				onStatusChange={onStatusChange}
				mode="text"
			/>,
		);

		// Fast-forward past the initial 10ms delay in initiate()
		await act(async () => {
			vi.advanceTimersByTime(20);
		});

		// Exhaust 3 retries
		// retryDelay is 1000 * 2**retryCount
		// retries: 0 (delay 1s), 1 (delay 2s), 2 (delay 4s)
		for (let i = 0; i < 4; i++) {
			await act(async () => {
				mockES.emitError(new Error("SSE Failure"));
			});
			if (i < 3) {
				await act(async () => {
					vi.advanceTimersByTime(1000 * 2 ** i + 50);
				});
			}
		}

		expect(onStatusChange).toHaveBeenCalledWith("error");
		vi.useRealTimers();
	});
});

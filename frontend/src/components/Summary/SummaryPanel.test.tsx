import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SummaryPanel from "./SummaryPanel";

// Mock hooks
const mockGetCachedPaper = vi.fn();
const mockSavePaperToCache = vi.fn();

vi.mock("../../db/hooks", () => ({
	usePaperCache: () => ({
		getCachedPaper: mockGetCachedPaper,
		savePaperToCache: mockSavePaperToCache,
	}),
}));

const mockStartLoading = vi.fn();
const mockStopLoading = vi.fn();

vi.mock("../../contexts/LoadingContext", () => ({
	useLoading: () => ({
		startLoading: mockStartLoading,
		stopLoading: mockStopLoading,
	}),
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
		user: { uid: "test-user" },
	}),
}));

vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "ja" },
	}),
}));

// Mock components
vi.mock("../Common/MarkdownContent", () => ({
	default: ({ children }: { children: string }) => <div>{children}</div>,
}));

vi.mock("../Common/CopyButton", () => ({
	default: () => <button type="button">Copy</button>,
}));

vi.mock("../Common/FeedbackSection", () => ({
	default: () => <div>Feedback</div>,
}));

describe("SummaryPanel", () => {
	const defaultProps = {
		sessionId: "test-session",
		paperId: "test-paper",
	};

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		mockGetCachedPaper.mockResolvedValue(undefined);
	});

	it("renders loading/generating state initially when paperId is present", async () => {
		render(<SummaryPanel {...defaultProps} />);
		expect(screen.getByText("summary.generating")).toBeDefined();
	});

	it("renders empty state with generate button when paperId is missing", async () => {
		render(<SummaryPanel {...defaultProps} paperId={null} />);
		expect(screen.getByText("summary.hints.summary")).toBeDefined();
		expect(screen.getByText("summary.generate")).toBeDefined();
	});

	it("renders loading state when isAnalyzing is true", () => {
		render(<SummaryPanel {...defaultProps} isAnalyzing={true} />);
		expect(screen.getByText("summary.generating")).toBeDefined();
	});

	it("loads summary from cache on mount", async () => {
		mockGetCachedPaper.mockResolvedValue({
			full_summary: "Cached Summary Content",
		});

		render(<SummaryPanel {...defaultProps} />);

		await waitFor(() => {
			expect(screen.getByText("Cached Summary Content")).toBeDefined();
		});
		expect(mockGetCachedPaper).toHaveBeenCalledWith("test-paper");
	});

	it("fetches summary when generate button is clicked", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({
				summary: "Newly Generated Summary",
				trace_id: "test-trace",
			}),
		});

		render(<SummaryPanel {...defaultProps} paperId={null} />);

		const generateButton = screen.getByText("summary.generate");
		fireEvent.click(generateButton);

		expect(mockStartLoading).toHaveBeenCalled();

		await waitFor(() => {
			expect(screen.getByText("Newly Generated Summary")).toBeDefined();
		});

		expect(mockStopLoading).toHaveBeenCalled();
	});

	it("handles auto-fetch when isAnalyzing transitions from true to false", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({ summary: "Auto Action Summary" }),
		});

		const { rerender } = render(
			<SummaryPanel {...defaultProps} isAnalyzing={true} />,
		);

		// Should not fetch while analyzing
		expect(global.fetch).not.toHaveBeenCalled();

		// Transition to not analyzing
		rerender(<SummaryPanel {...defaultProps} isAnalyzing={false} />);

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalled();
			expect(screen.getByText("Auto Action Summary")).toBeDefined();
		});
	});

	it("handles auto-fetch when isActive becomes true and no summary exists", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({ summary: "Active Tab Summary" }),
		});

		const { rerender } = render(
			<SummaryPanel {...defaultProps} isActive={false} />,
		);

		expect(global.fetch).not.toHaveBeenCalled();

		rerender(<SummaryPanel {...defaultProps} isActive={true} />);

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalled();
		});
	});

	it("shows error message on fetch failure", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: false,
			status: 500,
			text: async () => "Internal Server Error",
		});

		render(<SummaryPanel {...defaultProps} paperId={null} />);

		const generateButton = screen.getByText("summary.generate");
		fireEvent.click(generateButton);

		await waitFor(() => {
			expect(screen.getByText("common.errors.processing")).toBeDefined();
		});
	});

	it("regenerates when regenerate button is clicked with force=true", async () => {
		// First, load a summary
		mockGetCachedPaper.mockResolvedValue({
			full_summary: "Old Summary",
		});

		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({ summary: "New Forced Summary" }),
		});

		render(<SummaryPanel {...defaultProps} />);

		await waitFor(() => {
			expect(screen.getByText("Old Summary")).toBeDefined();
		});

		const regenerateButton = screen.getByTitle("summary.regenerate");
		fireEvent.click(regenerateButton);

		await waitFor(() => {
			expect(screen.getByText("New Forced Summary")).toBeDefined();
		});

		// Check fetch call body for force=true
		const lastFetchCallArgs = (global.fetch as any).mock.calls[0];
		const formData = lastFetchCallArgs[1].body as FormData;
		expect(formData.get("force")).toBe("true");
	});

	it("handles MD download button click", async () => {
		mockGetCachedPaper.mockResolvedValue({
			full_summary: "Content to download",
		});

		// Mock URL functions
		global.URL.createObjectURL = vi.fn().mockReturnValue("blob:url");
		global.URL.revokeObjectURL = vi.fn();

		// Mock a.click by spying on the element directly after creation
		const mockClick = vi.fn();
		const originalCreateElement = document.createElement;
		const spy = vi
			.spyOn(document, "createElement")
			.mockImplementation((tagName) => {
				const element = originalCreateElement.call(document, tagName);
				if (tagName === "a") {
					vi.spyOn(element, "click").mockImplementation(mockClick);
				}
				return element;
			});

		render(<SummaryPanel {...defaultProps} />);

		await waitFor(() => {
			expect(screen.getByText("Content to download")).toBeDefined();
		});

		const downloadButton = screen.getByTitle("Markdownでダウンロード");
		fireEvent.click(downloadButton);

		expect(mockClick).toHaveBeenCalled();
		expect(global.URL.createObjectURL).toHaveBeenCalled();

		spy.mockRestore();
	});
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dictionary from "./Dictionary";

// Mock the hooks
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "ja" },
	}),
}));

vi.mock("../../lib/logger", () => ({
	createLogger: () => ({
		info: vi.fn(),
		error: vi.fn(),
		debug: vi.fn(),
	}),
}));

// Mock components that might be complex
vi.mock("../Common/MarkdownContent", () => ({
	default: ({ children }: { children: string }) => <div>{children}</div>,
}));

vi.mock("../Common/CopyButton", () => ({
	default: () => <button type="button">Copy</button>,
}));

vi.mock("../Common/FeedbackSection", () => ({
	default: () => <div>Feedback</div>,
}));

vi.mock("../FigureInsight/FigureInsight", () => ({
	default: () => <div>Figure Insight</div>,
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
		user: { uid: "test-user" },
		loading: false,
		isGuest: false,
	}),
}));

describe("Dictionary Component", () => {
	const defaultProps = {
		sessionId: "test-session",
		paperId: "test-paper",
	};

	beforeEach(() => {
		vi.clearAllMocks();
		// Reset fetch mock
		global.fetch = vi.fn();
	});

	it("renders empty state initially", () => {
		render(<Dictionary {...defaultProps} />);
		expect(screen.getByText("viewer.dictionary.ready")).toBeDefined();
	});

	it("renders external link UI when a URL is passed", () => {
		render(<Dictionary {...defaultProps} term="https://google.com" />);
		expect(screen.getByText("viewer.dictionary.external_link")).toBeDefined();
		expect(screen.getByText("viewer.dictionary.open_link")).toBeDefined();
	});

	it("fetches definition when term is provided", async () => {
		const mockResponse = {
			word: "hello",
			translation: "こんにちは",
			source: "Local-MT",
		};

		(global.fetch as any).mockResolvedValue({
			ok: true,
			headers: { get: () => "application/json" },
			json: async () => mockResponse,
		});

		render(<Dictionary {...defaultProps} term="hello" />);

		// Should show processing first (Analyzing state)
		expect(screen.getByText("summary.processing")).toBeDefined();

		await waitFor(() => {
			expect(screen.getByText("こんにちは")).toBeDefined();
		});

		expect(screen.getByText("hello")).toBeDefined();
		expect(screen.getByText("Local-MT")).toBeDefined();
	});

	it("switches to explanation tab", async () => {
		// Mock initial fetch for translation
		(global.fetch as any).mockResolvedValue({
			ok: true,
			headers: { get: () => "application/json" },
			json: async () => ({
				word: "hello",
				translation: "Hello translation",
				source: "Local-MT",
			}),
		});

		render(<Dictionary {...defaultProps} term="hello" />);

		await waitFor(() => {
			expect(screen.getByText("Hello translation")).toBeDefined();
		});

		// Mock fetch for explanation
		(global.fetch as any).mockResolvedValue({
			ok: true,
			headers: { get: () => "application/json" },
			json: async () => ({
				word: "hello",
				translation: "Deep explanation",
				source: "Gemini",
			}),
		});

		// Find Explanation tab and click
		const explanationTab = screen.getByText(/sidebar.tabs.explanation/);
		fireEvent.click(explanationTab);

		// Wait for explanation result
		await waitFor(() => {
			expect(screen.getByText("Deep explanation")).toBeDefined();
		});

		expect(screen.getByText("Gemini")).toBeDefined();
	});

	it("handles fetch error gracefully", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: false,
			status: 404,
			text: async () => "Not Found",
		});

		render(<Dictionary {...defaultProps} term="unknown-word" />);

		await waitFor(() => {
			expect(screen.getByText(/Definition not found/)).toBeDefined();
		});
	});

	it("shows figure insight when figures tab is selected", () => {
		render(<Dictionary {...defaultProps} />);

		const figuresTab = screen.getByText(/sidebar.tabs.figures/);
		fireEvent.click(figuresTab);

		expect(screen.getByText("Figure Insight")).toBeDefined();
	});
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as recommendationLib from "@/lib/recommendation";
import DiscoverPanel from "./DiscoverPanel";

// Mock dependencies
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
	}),
}));

vi.mock("../Common/CopyButton", () => ({
	default: () => (
		<button type="button" data-testid="copy-button">
			Copy
		</button>
	),
}));

vi.mock("../Common/FeedbackSection", () => ({
	default: () => <div data-testid="feedback-section">Feedback</div>,
}));

vi.mock("../Common/MarkdownContent", () => ({
	default: ({ children }: any) => (
		<div data-testid="markdown-content">{children}</div>
	),
}));

// Mock recommendation lib
vi.mock("@/lib/recommendation", () => ({
	generateRecommendations: vi.fn(),
}));

describe("DiscoverPanel", () => {
	beforeEach(() => {
		vi.resetAllMocks();
	});

	it("renders search input and generate button initially", () => {
		render(<DiscoverPanel sessionId="s1" />);
		expect(
			screen.getByPlaceholderText("recommendation.user_query_placeholder"),
		).toBeDefined();
		expect(screen.getByText("summary.generate_recommend")).toBeDefined();
	});

	it("fetches and displays recommendations", async () => {
		const mockResponse = {
			recommendations: [
				{
					title: "Paper A",
					abstract: "Abstract A",
					authors: [{ name: "Author X" }],
					year: 2024,
					url: "http://example.com/a",
				},
			],
			reasoning: "Because you like AI",
			trace_id: "tr_rec_123",
		};

		(recommendationLib.generateRecommendations as any).mockResolvedValue(
			mockResponse,
		);

		render(<DiscoverPanel sessionId="s1" />);

		const textarea = screen.getByPlaceholderText(
			"recommendation.user_query_placeholder",
		);
		fireEvent.change(textarea, { target: { value: "AI papers" } });

		const generateBtn = screen.getByText("summary.generate_recommend");
		fireEvent.click(generateBtn);

		expect(screen.getByText("recommendation.analyzing")).toBeDefined();

		await waitFor(() => {
			expect(screen.getByText("Paper A")).toBeDefined();
		});

		expect(screen.getByText("Abstract A")).toBeDefined();
		expect(screen.getByText("Author X (2024)")).toBeDefined();
		expect(recommendationLib.generateRecommendations).toHaveBeenCalledWith(
			"s1",
			"test-token",
			"AI papers",
		);
	});

	it("handles reset/start over", async () => {
		(recommendationLib.generateRecommendations as any).mockResolvedValue({
			recommendations: [{ title: "Paper A", abstract: "A" }],
			trace_id: "tr1",
		});

		render(<DiscoverPanel sessionId="s1" />);

		fireEvent.click(screen.getByText("summary.generate_recommend"));

		await waitFor(() => {
			expect(screen.getByText("Paper A")).toBeDefined();
		});

		const startOverBtn = screen.getByText("Start Over");
		fireEvent.click(startOverBtn);

		expect(screen.getByText("summary.generate_recommend")).toBeDefined();
		expect(screen.queryByText("Paper A")).toBeNull();
	});

	it("handles error during generation", async () => {
		(recommendationLib.generateRecommendations as any).mockRejectedValue(
			new Error("Network Error"),
		);

		render(<DiscoverPanel sessionId="s1" />);

		fireEvent.click(screen.getByText("summary.generate_recommend"));

		await waitFor(() => {
			expect(
				screen.getByText("error.load_recommendations_failed"),
			).toBeDefined();
		});
	});
});

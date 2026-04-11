import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as recommendationLib from "@/lib/recommendation";
import RecommendationTab from "./RecommendationTab";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, defaultValue?: string) => defaultValue || key,
	}),
}));

// Mock AuthContext
vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
	}),
}));

// Mock FeedbackSection (to avoid testing it here)
vi.mock("../Common/FeedbackSection", () => ({
	default: () => <div data-testid="feedback-section" />,
}));

// Mock recommendation lib
vi.mock("@/lib/recommendation", () => ({
	generateRecommendations: vi.fn(),
}));

describe("RecommendationTab Component", () => {
	const sessionId = "test-session-id";

	beforeEach(() => {
		vi.clearAllMocks();
		// Mock window.open
		vi.stubGlobal("open", vi.fn());
	});

	it("renders initial state correctly", () => {
		render(<RecommendationTab sessionId={sessionId} />);
		expect(screen.getByText("Explore Next Papers")).toBeDefined();
		expect(screen.getByText("Generate Recommendations")).toBeDefined();
	});

	it("calls generateRecommendations when button is clicked", async () => {
		const mockResponse = {
			recommendations: [
				{
					title: "Paper 1",
					authors: [{ name: "Author 1" }],
					year: 2023,
					abstract: "This is a test abstract 1",
					url: "https://example.com/1",
				},
			],
		};
		vi.mocked(recommendationLib.generateRecommendations).mockResolvedValue(
			mockResponse as any,
		);

		render(<RecommendationTab sessionId={sessionId} />);

		const generateButton = screen.getByText("Generate Recommendations");
		fireEvent.click(generateButton);

		expect(recommendationLib.generateRecommendations).toHaveBeenCalledWith(
			sessionId,
			"test-token",
			undefined,
		);

		// Check for loading state
		expect(
			screen.getByText("Analyzing user profile and generating insights..."),
		).toBeDefined();

		// Check for results
		await waitFor(() => {
			expect(screen.getByText("Paper 1")).toBeDefined();
			expect(screen.getByText("Author 1 (2023)")).toBeDefined();
			expect(screen.getByText("This is a test abstract 1")).toBeDefined();
		});
	});

	it("handles failure of generateRecommendations", async () => {
		vi.mocked(recommendationLib.generateRecommendations).mockRejectedValue(
			new Error("API Error"),
		);

		render(<RecommendationTab sessionId={sessionId} />);

		const generateButton = screen.getByText("Generate Recommendations");
		fireEvent.click(generateButton);

		await waitFor(() => {
			expect(
				screen.getByText(
					"Failed to generate recommendations. Please try again.",
				),
			).toBeDefined();
		});
	});

	it("handles paper click and opens window", async () => {
		const mockResponse = {
			recommendations: [
				{
					title: "Paper 1",
					authors: [{ name: "Author 1" }],
					year: 2023,
					abstract: "This is a test abstract 1",
					url: "https://example.com/1",
				},
			],
		};
		vi.mocked(recommendationLib.generateRecommendations).mockResolvedValue(
			mockResponse as any,
		);

		render(<RecommendationTab sessionId={sessionId} />);
		fireEvent.click(screen.getByText("Generate Recommendations"));

		await waitFor(() => {
			expect(screen.getByText("Paper 1")).toBeDefined();
		});

		const exploreButton = screen.getByText("Explore");
		fireEvent.click(exploreButton);

		expect(window.open).toHaveBeenCalledWith(
			"https://example.com/1",
			"_blank",
			"noopener,noreferrer",
		);
		expect(screen.getByText("Clicked")).toBeDefined();
	});

	it("falls back to Google Scholar if no URL is provided", async () => {
		const mockResponse = {
			recommendations: [
				{
					title: "Paper 2",
					authors: [{ name: "Author 2" }],
					year: 2024,
					abstract: "This is a test abstract 2",
				},
			],
		};
		vi.mocked(recommendationLib.generateRecommendations).mockResolvedValue(
			mockResponse as any,
		);

		render(<RecommendationTab sessionId={sessionId} />);
		fireEvent.click(screen.getByText("Generate Recommendations"));

		await waitFor(() => {
			const exploreButton = screen.getByText("Explore");
			fireEvent.click(exploreButton);
		});

		expect(window.open).toHaveBeenCalledWith(
			expect.stringContaining("https://scholar.google.com/scholar?q=Paper%202"),
			"_blank",
			"noopener,noreferrer",
		);
	});

	it("resets state when Start Over is clicked", async () => {
		const mockResponse = {
			recommendations: [
				{
					title: "Paper 1",
					authors: [],
					abstract: "...",
				},
			],
		};
		vi.mocked(recommendationLib.generateRecommendations).mockResolvedValue(
			mockResponse as any,
		);

		render(<RecommendationTab sessionId={sessionId} />);
		fireEvent.click(screen.getByText("Generate Recommendations"));

		await waitFor(() => {
			expect(screen.getByText("Paper 1")).toBeDefined();
		});

		const startOverButton = screen.getByText("Start Over");
		fireEvent.click(startOverButton);

		expect(screen.getByText("Explore Next Papers")).toBeDefined();
		expect(screen.queryByText("Paper 1")).toBeNull();
	});
});

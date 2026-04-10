import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CritiquePanel from "./CritiquePanel";

// Mock dependencies
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "ja" },
	}),
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
	}),
}));

vi.mock("../../contexts/LoadingContext", () => ({
	useLoading: () => ({
		startLoading: vi.fn(),
		stopLoading: vi.fn(),
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

describe("CritiquePanel", () => {
	beforeEach(() => {
		vi.resetAllMocks();
		global.fetch = vi.fn();
	});

	it("renders initial state with a start button", () => {
		render(<CritiquePanel sessionId="s1" paperId="p1" />);
		expect(screen.getByText("summary.start_critique")).toBeDefined();
	});

	it("calls API and renders result on button click", async () => {
		const mockResponse = {
			overall_assessment: "Great paper",
			hidden_assumptions: [{ assumption: "A1", risk: "R1" }],
			trace_id: "tr123",
		};

		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => mockResponse,
		});

		render(<CritiquePanel sessionId="s1" paperId="p1" />);

		const startBtn = screen.getByText("summary.start_critique");
		fireEvent.click(startBtn);

		await waitFor(() => {
			expect(screen.getByText("Great paper")).toBeDefined();
		});

		expect(screen.getByText("● A1")).toBeDefined();
		expect(screen.getByText("R1")).toBeDefined();
	});

	it("handles missing elective fields gracefully", async () => {
		const mockResponse = {
			overall_assessment: "Minimal result",
			trace_id: "tr456",
			// missing other fields
		};

		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => mockResponse,
		});

		render(<CritiquePanel sessionId="s1" paperId="p1" />);

		fireEvent.click(screen.getByText("summary.start_critique"));

		await waitFor(() => {
			expect(screen.getByText("Minimal result")).toBeDefined();
		});

		// Check that optional headers are NOT present
		expect(screen.queryByText("summary.assumptions")).toBeNull();
		expect(screen.queryByText("summary.unverified")).toBeNull();
		expect(screen.queryByText("summary.reproducibility")).toBeNull();
	});

	it("handles API error", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: false,
			status: 500,
			text: async () => "External Error",
		});

		render(<CritiquePanel sessionId="s1" paperId="p1" />);

		fireEvent.click(screen.getByText("summary.start_critique"));

		await waitFor(() => {
			expect(screen.getByText("common.errors.processing")).toBeDefined();
		});
	});
});

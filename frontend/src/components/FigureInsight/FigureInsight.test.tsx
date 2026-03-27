import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../../contexts/AuthContext";
import type { SelectedFigure } from "../PDF/types";
import FigureInsight from "./FigureInsight";

// Mock dependencies
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "ja" },
	}),
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: vi.fn(),
}));

describe("FigureInsight Component", () => {
	const mockFigure: SelectedFigure = {
		id: "fig1",
		image_url: "http://example.com/fig1.jpg",
		page_number: 1,
		label: "figure",
	};

	beforeEach(() => {
		vi.resetAllMocks();
		global.fetch = vi.fn();
		(useAuth as any).mockReturnValue({
			token: "test-token",
		});
	});

	it("renders empty state when no figure is selected and stack is empty", () => {
		render(<FigureInsight sessionId="session1" />);
		expect(screen.getByText("図をクリックして解説")).toBeDefined();
		expect(
			screen.getByText(/クリックモードで論文中の図・表をクリックすると/),
		).toBeDefined();
	});

	it("starts analysis when a new figure is selected", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({
				explanation: "Test explanation",
				trace_id: "trace1",
			}),
		});

		const { rerender } = render(<FigureInsight sessionId="session2" />);

		// Select a figure
		rerender(
			<FigureInsight sessionId="session2" selectedFigure={mockFigure} />,
		);

		// Should show loading state (can be multiple occurrences in different parts of the card)
		expect(screen.getAllByText("AIが解析中...").length).toBeGreaterThan(0);

		// Wait for explanation
		await waitFor(() => {
			expect(screen.getByText("Test explanation")).toBeDefined();
		});

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/figures/fig1/explain"),
			expect.anything(),
		);
	});

	it("shows error message when initial fetch fails", async () => {
		(global.fetch as any).mockRejectedValue(new Error("Network Error"));

		const { rerender } = render(<FigureInsight sessionId="session3" />);
		rerender(
			<FigureInsight sessionId="session3" selectedFigure={mockFigure} />,
		);

		await waitFor(() => {
			expect(
				screen.getByText("viewer.figure_analysis_network_error"),
			).toBeDefined();
		});
	});

	it("clears stack when clear button is clicked", async () => {
		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => ({ explanation: "Expl", trace_id: "t" }),
		});

		const { rerender } = render(
			<FigureInsight sessionId="session4" selectedFigure={mockFigure} />,
		);

		await waitFor(() => {
			expect(screen.getByText("Expl")).toBeDefined();
		});

		// Select another figure
		const mockFigure2 = { ...mockFigure, id: "fig2" };
		rerender(
			<FigureInsight sessionId="session4" selectedFigure={mockFigure2} />,
		);

		await waitFor(() => {
			expect(screen.getByText("2件の図解")).toBeDefined();
		});

		const clearButton = screen.getByText("すべてクリア");
		fireEvent.click(clearButton);

		expect(screen.queryByText("2件の図解")).toBeNull();
		// Note: since mockFigure is still in props, it might still render the container but empty.
		// Rerender with null to see the empty state
		rerender(<FigureInsight sessionId="session4" selectedFigure={null} />);
		expect(screen.getByText("図をクリックして解説")).toBeDefined();
	});
});

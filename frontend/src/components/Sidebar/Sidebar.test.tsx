import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, defaultValue?: string) => defaultValue || key,
	}),
}));

// Mock sub-components to avoid dependency issues
vi.mock("../Chat/ChatWindow", () => ({
	default: () => <div data-testid="chat-window">Chat Window</div>,
}));
vi.mock("../Dictionary/Dictionary", () => ({
	default: () => <div data-testid="dictionary">Dictionary</div>,
}));
vi.mock("../Notes/NoteList", () => ({
	default: () => <div data-testid="note-list">Note List</div>,
}));
vi.mock("../Summary/Summary", () => ({
	default: () => <div data-testid="summary">Summary</div>,
}));

describe("Sidebar Component", () => {
	const defaultProps = {
		sessionId: "test-session",
		activeTab: "notes",
		onTabChange: vi.fn(),
		paperId: "paper-123",
	};

	it("renders all tabs", () => {
		render(<Sidebar {...defaultProps} />);

		expect(screen.getByText("sidebar.tabs.notes")).toBeDefined();
		expect(screen.getByText("sidebar.tabs.analysis")).toBeDefined();
		expect(screen.getByText("sidebar.tabs.chat")).toBeDefined();
		expect(screen.getByText("sidebar.tabs.comments")).toBeDefined();
	});

	it("shows the active tab content", () => {
		const { rerender } = render(
			<Sidebar {...defaultProps} activeTab="notes" />,
		);

		// In Sidebar.tsx, it uses opacity and pointer-events to hide/show
		// The active one should have opacity-100 z-10
		const dictContainer = screen.getByTestId("dictionary").parentElement;
		expect(dictContainer?.className).toContain("opacity-100");

		rerender(<Sidebar {...defaultProps} activeTab="analysis" />);
		const summaryContainer = screen.getByTestId("summary").parentElement;
		expect(summaryContainer?.className).toContain("opacity-100");
	});

	it("calls onTabChange when a tab is clicked", () => {
		render(<Sidebar {...defaultProps} />);

		fireEvent.click(screen.getByText("sidebar.tabs.chat"));
		expect(defaultProps.onTabChange).toHaveBeenCalledWith("chat");
	});

	it("calls onClose when close button is clicked", () => {
		const onClose = vi.fn();
		render(<Sidebar {...defaultProps} onClose={onClose} />);

		// Since it's md:hidden, we might need to check if it's rendered
		const closeButton = screen.getByTitle("Close panel");
		fireEvent.click(closeButton);
		expect(onClose).toHaveBeenCalled();
	});
});

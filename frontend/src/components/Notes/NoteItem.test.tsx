import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NoteItem from "./NoteItem";
import type { Note } from "./types";

// Mock the hooks and components
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, options?: any) => {
			if (key === "notes.jump_to_page") return `Jump to page ${options.page}`;
			return key;
		},
	}),
}));

vi.mock("../Common/CopyButton", () => ({
	default: ({ text }: { text: string }) => (
		<button type="button" data-testid="copy-button">
			{text}
		</button>
	),
}));

vi.mock("../Common/MarkdownContent", () => ({
	default: ({ children }: { children: string }) => (
		<div data-testid="markdown-content">{children}</div>
	),
}));

describe("NoteItem Component", () => {
	const mockNote: Note = {
		note_id: "note-123",
		session_id: "session-123",
		term: "AI",
		note: "Artificial Intelligence",
		created_at: "2024-01-01T12:00:00Z",
	};

	const mockOnDelete = vi.fn();
	const mockOnJump = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders note content correctly", () => {
		render(<NoteItem note={mockNote} onDelete={mockOnDelete} />);

		expect(screen.getByText("AI")).toBeDefined();
		expect(screen.getByTestId("markdown-content")).toHaveTextContent(
			"Artificial Intelligence",
		);
	});

	it("calls onDelete when delete button is clicked", () => {
		render(<NoteItem note={mockNote} onDelete={mockOnDelete} />);

		const deleteBtn = screen.getByTitle("Delete Note");
		fireEvent.click(deleteBtn);

		expect(mockOnDelete).toHaveBeenCalledWith("note-123");
	});

	it("shows image when image_url is provided", () => {
		const noteWithImage = {
			...mockNote,
			image_url: "http://example.com/img.jpg",
		};
		render(<NoteItem note={noteWithImage} onDelete={mockOnDelete} />);

		const img = screen.getByAltText("Note Attachment");
		expect(img).toBeDefined();
		expect(img.getAttribute("src")).toBe("http://example.com/img.jpg");
	});

	it("shows jump button when page_number is provided", () => {
		const noteWithPage = { ...mockNote, page_number: 5, x: 0.1, y: 0.2 };
		render(
			<NoteItem
				note={noteWithPage}
				onDelete={mockOnDelete}
				onJump={mockOnJump}
			/>,
		);

		const jumpBtn = screen.getByText("Jump to page 5");
		expect(jumpBtn).toBeDefined();

		fireEvent.click(jumpBtn);
		expect(mockOnJump).toHaveBeenCalledWith(5, 0.1, 0.2, "AI");
	});

	it("does not show jump button when page_number is missing", () => {
		render(<NoteItem note={mockNote} onDelete={mockOnDelete} />);
		expect(screen.queryByText(/Jump to page/)).toBeNull();
	});
});

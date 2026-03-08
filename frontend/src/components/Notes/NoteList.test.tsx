import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NoteList from "./NoteList";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, defaultValue?: string) => defaultValue || key,
	}),
}));

// Mock AuthContext
vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: "test-token",
	}),
}));

// Mock AddNoteForm and NoteItem to simplify
vi.mock("./AddNoteForm", () => ({
	default: ({ onAdd }: any) => (
		<div data-testid="add-note-form">
			<button type="button" onClick={() => onAdd("New Term", "New Note")}>
				Add Mock Note
			</button>
		</div>
	),
}));
vi.mock("./NoteItem", () => ({
	default: ({ note, onDelete }: any) => (
		<div data-testid="note-item">
			{note.term}: {note.note}
			<button type="button" onClick={() => onDelete(note.note_id)}>
				Delete
			</button>
		</div>
	),
}));

describe("NoteList Component", () => {
	const props = {
		sessionId: "session-123",
		paperId: "paper-456",
		onJump: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
		vi.stubGlobal("fetch", vi.fn());
	});

	it("fetches and displays notes on mount", async () => {
		const mockNotes = {
			notes: [
				{ note_id: "1", term: "Term 1", note: "Note 1" },
				{ note_id: "2", term: "Term 2", note: "Note 2" },
			],
		};
		vi.mocked(fetch).mockResolvedValue({
			ok: true,
			json: async () => mockNotes,
		} as Response);

		render(<NoteList {...props} />);

		await waitFor(() => {
			expect(screen.getByText("Term 1: Note 1")).toBeDefined();
			expect(screen.getByText("Term 2: Note 2")).toBeDefined();
		});

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/note/session-123?paper_id=paper-456"),
			expect.any(Object),
		);
	});

	it("displays no notes message when empty", async () => {
		vi.mocked(fetch).mockResolvedValue({
			ok: true,
			json: async () => ({ notes: [] }),
		} as Response);

		render(<NoteList {...props} />);

		await waitFor(() => {
			expect(screen.getByText("notes.no_notes")).toBeDefined();
		});
	});

	it("calls POST when adding a note", async () => {
		vi.mocked(fetch).mockResolvedValue({
			ok: true,
			json: async () => ({ notes: [] }),
		} as Response);

		render(<NoteList {...props} />);

		const addButton = screen.getByText("Add Mock Note");
		fireEvent.click(addButton);

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/note"),
			expect.objectContaining({
				method: "POST",
				body: expect.stringContaining("New Term"),
			}),
		);
	});

	it("calls DELETE when deleting a note", async () => {
		const mockNotes = {
			notes: [{ note_id: "1", term: "Term 1", note: "Note 1" }],
		};
		vi.mocked(fetch).mockResolvedValue({
			ok: true,
			json: async () => mockNotes,
		} as Response);

		render(<NoteList {...props} />);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeDefined();
		});

		const deleteButton = screen.getByText("Delete");
		fireEvent.click(deleteButton);

		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining("/api/note/1"),
			expect.objectContaining({
				method: "DELETE",
			}),
		);
	});
});

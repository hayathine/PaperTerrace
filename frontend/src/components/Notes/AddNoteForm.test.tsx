import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AddNoteForm from "./AddNoteForm";

// Mock the hooks
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

describe("AddNoteForm Component", () => {
	const mockOnAdd = vi.fn().mockResolvedValue(undefined);
	const mockOnUpdate = vi.fn().mockResolvedValue(undefined);
	const mockOnCancelEdit = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders efficiently in add mode", () => {
		render(<AddNoteForm onAdd={mockOnAdd} />);

		expect(screen.getByPlaceholderText("notes.placeholder_term")).toBeDefined();
		expect(
			screen.getByPlaceholderText("notes.placeholder_content"),
		).toBeDefined();
		expect(screen.getByText("notes.add")).toBeDefined();
	});

	it("submits the form with term and note", async () => {
		render(<AddNoteForm onAdd={mockOnAdd} />);

		const termInput = screen.getByPlaceholderText("notes.placeholder_term");
		const noteInput = screen.getByPlaceholderText("notes.placeholder_content");
		const submitBtn = screen.getByText("notes.add");

		fireEvent.change(termInput, { target: { value: "Test Term" } });
		fireEvent.change(noteInput, { target: { value: "Test Note" } });
		fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(mockOnAdd).toHaveBeenCalledWith(
				"Test Term",
				"Test Note",
				undefined,
				undefined,
			);
		});

		// Inputs should be cleared after successful add
		expect((termInput as HTMLInputElement).value).toBe("");
		expect((noteInput as HTMLTextAreaElement).value).toBe("");
	});

	it("renders in edit mode when editingNote is provided", () => {
		const editingNote = {
			id: "note-1",
			term: "Existing Term",
			note: "Existing Note",
		};

		render(
			<AddNoteForm
				onAdd={mockOnAdd}
				onUpdate={mockOnUpdate}
				editingNote={editingNote}
				onCancelEdit={mockOnCancelEdit}
			/>,
		);

		expect(
			(
				screen.getByPlaceholderText(
					"notes.placeholder_term",
				) as HTMLInputElement
			).value,
		).toBe("Existing Term");
		expect(
			(
				screen.getByPlaceholderText(
					"notes.placeholder_content",
				) as HTMLTextAreaElement
			).value,
		).toBe("Existing Note");
		expect(screen.getByText("notes.update")).toBeDefined();
		expect(screen.getByText("common.cancel")).toBeDefined();
	});

	it("calls onUpdate when submitting in edit mode", async () => {
		const editingNote = {
			id: "note-1",
			term: "Existing Term",
			note: "Existing Note",
		};

		render(
			<AddNoteForm
				onAdd={mockOnAdd}
				onUpdate={mockOnUpdate}
				editingNote={editingNote}
			/>,
		);

		const termInput = screen.getByPlaceholderText("notes.placeholder_term");
		fireEvent.change(termInput, { target: { value: "Updated Term" } });
		fireEvent.click(screen.getByText("notes.update"));

		await waitFor(() => {
			expect(mockOnUpdate).toHaveBeenCalledWith(
				"note-1",
				"Updated Term",
				"Existing Note",
				undefined,
				undefined,
			);
		});
	});

	it("calls onCancelEdit when cancel button is clicked", () => {
		const editingNote = {
			id: "note-1",
			term: "Existing Term",
			note: "Existing Note",
		};

		render(
			<AddNoteForm
				onAdd={mockOnAdd}
				onUpdate={mockOnUpdate}
				editingNote={editingNote}
				onCancelEdit={mockOnCancelEdit}
			/>,
		);

		fireEvent.click(screen.getByText("common.cancel"));
		expect(mockOnCancelEdit).toHaveBeenCalled();
	});

	it("disables submit button when term is empty", () => {
		render(<AddNoteForm onAdd={mockOnAdd} />);
		const submitBtn = screen.getByText("notes.add") as HTMLButtonElement;

		expect(submitBtn.disabled).toBe(true);

		const termInput = screen.getByPlaceholderText("notes.placeholder_term");
		fireEvent.change(termInput, { target: { value: "Something" } });
		// Still disabled because note/image is missing
		expect(submitBtn.disabled).toBe(true);

		const noteInput = screen.getByPlaceholderText("notes.placeholder_content");
		fireEvent.change(noteInput, { target: { value: "Some note" } });
		expect(submitBtn.disabled).toBe(false);
	});
});

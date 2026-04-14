import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DictionaryHistoryTab from "./DictionaryHistoryTab";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

describe("DictionaryHistoryTab Component", () => {
	const mockSavedNotes = [
		{
			note_id: "1",
			term: "hello",
			note: "a greeting",
			page_number: 1,
			user_id: "user1",
			created_at: "2024-01-01",
		},
		{
			note_id: "2",
			term: "world",
			note: "the planet",
			page_number: 2,
			user_id: "user1",
			created_at: "2024-01-02",
		},
	];

	it("renders empty state when no notes are provided", () => {
		render(<DictionaryHistoryTab savedNotes={[]} onSelectNote={() => {}} />);

		expect(screen.getByText("viewer.dictionary.history_empty")).toBeDefined();
		expect(screen.getByText("viewer.dictionary.history_hint")).toBeDefined();
	});

	it("renders a list of saved notes", () => {
		render(
			<DictionaryHistoryTab
				savedNotes={mockSavedNotes}
				onSelectNote={() => {}}
			/>,
		);

		expect(screen.getByText("hello")).toBeDefined();
		expect(screen.getByText("world")).toBeDefined();
		expect(screen.getByText("a greeting")).toBeDefined();
		expect(screen.getByText("p.1")).toBeDefined();
		expect(screen.getByText("p.2")).toBeDefined();
	});

	it("triggers onSelectNote with the correct note when a note is clicked", () => {
		const onSelectNote = vi.fn();
		render(
			<DictionaryHistoryTab
				savedNotes={mockSavedNotes}
				onSelectNote={onSelectNote}
			/>,
		);

		const helloNote = screen.getByText("hello").closest("button");
		if (helloNote) {
			fireEvent.click(helloNote);
		}

		expect(onSelectNote).toHaveBeenCalledTimes(1);
		expect(onSelectNote).toHaveBeenCalledWith(mockSavedNotes[0]);
	});

	it("renders note without page number correctly", () => {
		const notesWithoutPage = [
			{
				note_id: "3",
				term: "no-page",
				note: "some note",
				user_id: "user1",
				created_at: "2024-01-03",
			},
		];

		render(
			<DictionaryHistoryTab
				savedNotes={notesWithoutPage as any}
				onSelectNote={() => {}}
			/>,
		);

		expect(screen.getByText("no-page")).toBeDefined();
		expect(screen.queryByText(/p\./)).toBeNull();
	});
});

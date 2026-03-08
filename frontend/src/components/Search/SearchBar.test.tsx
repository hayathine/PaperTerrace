import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SearchBar from "./SearchBar";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, defaultValue?: string) => defaultValue || key,
	}),
}));

describe("SearchBar Component", () => {
	const defaultProps = {
		isOpen: true,
		onClose: vi.fn(),
		searchTerm: "",
		onSearchTermChange: vi.fn(),
		matches: [],
		currentMatchIndex: 0,
		onNextMatch: vi.fn(),
		onPrevMatch: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders when open", () => {
		render(<SearchBar {...defaultProps} />);
		expect(screen.getByPlaceholderText("検索...")).toBeDefined();
	});

	it("does not render when closed", () => {
		render(<SearchBar {...defaultProps} isOpen={false} />);
		expect(screen.queryByPlaceholderText("検索...")).toBeNull();
	});

	it("calls onSearchTermChange when typing", () => {
		render(<SearchBar {...defaultProps} />);
		const input = screen.getByPlaceholderText("検索...");
		fireEvent.change(input, { target: { value: "test" } });
		expect(defaultProps.onSearchTermChange).toHaveBeenCalledWith("test");
	});

	it("calls onNextMatch when Enter is pressed", () => {
		render(<SearchBar {...defaultProps} />);
		const input = screen.getByPlaceholderText("検索...");
		fireEvent.keyDown(input, { key: "Enter" });
		expect(defaultProps.onNextMatch).toHaveBeenCalled();
	});

	it("calls onPrevMatch when Shift+Enter is pressed", () => {
		render(<SearchBar {...defaultProps} />);
		const input = screen.getByPlaceholderText("検索...");
		fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
		expect(defaultProps.onPrevMatch).toHaveBeenCalled();
	});

	it("calls onClose when Escape is pressed", () => {
		render(<SearchBar {...defaultProps} />);
		const input = screen.getByPlaceholderText("検索...");
		fireEvent.keyDown(input, { key: "Escape" });
		expect(defaultProps.onClose).toHaveBeenCalled();
	});

	it("displays match counts correctly", () => {
		render(
			<SearchBar
				{...defaultProps}
				searchTerm="hello"
				matches={[
					{ page: 1, wordIndex: 0 },
					{ page: 2, wordIndex: 1 },
				]}
				currentMatchIndex={0}
			/>,
		);
		expect(screen.getByText("1 / 2")).toBeDefined();
	});
});

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InputArea from "./InputArea";

// Mock the hooks
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

describe("InputArea Component", () => {
	const mockOnSendMessage = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders correctly", () => {
		render(<InputArea onSendMessage={mockOnSendMessage} isLoading={false} />);
		expect(screen.getByPlaceholderText("chat.placeholder")).toBeDefined();
	});

	it("calls onSendMessage when clicking submit button", () => {
		render(<InputArea onSendMessage={mockOnSendMessage} isLoading={false} />);

		const input = screen.getByPlaceholderText("chat.placeholder");
		fireEvent.change(input, { target: { value: "Hello" } });

		const submitBtn = screen.getByRole("button");
		fireEvent.click(submitBtn);

		expect(mockOnSendMessage).toHaveBeenCalledWith("Hello");
		expect((input as HTMLTextAreaElement).value).toBe("");
	});

	it("calls onSendMessage when pressing Enter without Shift", () => {
		render(<InputArea onSendMessage={mockOnSendMessage} isLoading={false} />);

		const input = screen.getByPlaceholderText("chat.placeholder");
		fireEvent.change(input, { target: { value: "Hello world" } });

		fireEvent.keyDown(input, { key: "Enter", shiftKey: false });

		expect(mockOnSendMessage).toHaveBeenCalledWith("Hello world");
	});

	it("does not call onSendMessage when pressing Enter with Shift", () => {
		render(<InputArea onSendMessage={mockOnSendMessage} isLoading={false} />);

		const input = screen.getByPlaceholderText("chat.placeholder");
		fireEvent.change(input, { target: { value: "Hello" } });

		fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

		expect(mockOnSendMessage).not.toHaveBeenCalled();
	});

	it("disables input and button when isLoading is true", () => {
		render(<InputArea onSendMessage={mockOnSendMessage} isLoading={true} />);

		const input = screen.getByPlaceholderText("chat.placeholder");
		const submitBtn = screen.getByRole("button");

		expect(input).toBeDisabled();
		expect(submitBtn).toBeDisabled();
	});

	it("disables button when input is empty or whitespace", () => {
		render(<InputArea onSendMessage={mockOnSendMessage} isLoading={false} />);

		const submitBtn = screen.getByRole("button") as HTMLButtonElement;
		expect(submitBtn.disabled).toBe(true);

		const input = screen.getByPlaceholderText("chat.placeholder");
		fireEvent.change(input, { target: { value: "   " } });
		expect(submitBtn.disabled).toBe(true);
	});
});

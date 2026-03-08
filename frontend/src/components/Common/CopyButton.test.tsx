import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CopyButton from "./CopyButton";

describe("CopyButton Component", () => {
	const textToCopy = "Hello World";

	beforeEach(() => {
		vi.clearAllMocks();
		// Mock navigator.clipboard
		Object.assign(navigator, {
			clipboard: {
				writeText: vi.fn().mockImplementation(() => Promise.resolve()),
			},
		});
	});

	it("renders correctly", () => {
		render(<CopyButton text={textToCopy} />);
		expect(screen.getByRole("button")).toBeDefined();
	});

	it("copies text when clicked", async () => {
		render(<CopyButton text={textToCopy} />);
		const button = screen.getByRole("button");
		fireEvent.click(button);

		expect(navigator.clipboard.writeText).toHaveBeenCalledWith(textToCopy);

		await waitFor(() => {
			expect(screen.getByTitle("Copied!")).toBeDefined();
		});
	});

	it("returns to initial state after 2 seconds", async () => {
		vi.useFakeTimers();
		render(<CopyButton text={textToCopy} />);
		const button = screen.getByRole("button");
		fireEvent.click(button);

		// Handle the async part of handleCopy
		await vi.waitFor(() => {
			expect(screen.queryByTitle("Copied!")).not.toBeNull();
		});

		vi.advanceTimersByTime(3000);

		await vi.waitFor(() => {
			expect(screen.queryByTitle("Copy")).not.toBeNull();
		});
		vi.useRealTimers();
	});
});

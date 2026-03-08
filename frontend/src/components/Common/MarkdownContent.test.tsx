import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MarkdownContent from "./MarkdownContent";

// Simple mock for react-markdown to focus on our component's wrapper logic
vi.mock("react-markdown", () => ({
	default: ({ children }: { children: string }) => (
		<div data-testid="markdown">{children}</div>
	),
}));

describe("MarkdownContent Component", () => {
	it("renders children correctly", () => {
		const content = "## Hello World";
		render(<MarkdownContent>{content}</MarkdownContent>);
		expect(screen.getByTestId("markdown").textContent).toBe(content);
	});

	it("handles non-string children gracefully", () => {
		// @ts-expect-error - Testing invalid input
		render(<MarkdownContent>{null}</MarkdownContent>);
		expect(screen.getByTestId("markdown").textContent).toBe("");
	});

	it("applies className", () => {
		const className = "custom-class";
		render(<MarkdownContent className={className}>Text</MarkdownContent>);
		const container = screen.getByTestId("markdown").parentElement;
		expect(container?.className).toContain(className);
	});
});

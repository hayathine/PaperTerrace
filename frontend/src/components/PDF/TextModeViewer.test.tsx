import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TextModeViewer from "./TextModeViewer";

vi.mock("./TextModePage", () => ({
	default: ({ page }: { page: any }) => (
		<div data-testid={`page-${page.page_num}`}>Page {page.page_num}</div>
	),
}));

describe("TextModeViewer", () => {
	it("should render loading state when no pages are provided", () => {
		render(<TextModeViewer pages={[]} />);
		expect(screen.getByText("読み込み中...")).toBeDefined();
	});

	it("should render pages when provided", () => {
		const pages = [
			{ page_num: 1, lines: [] },
			{ page_num: 2, lines: [] },
		];
		render(<TextModeViewer pages={pages as any} />);

		expect(screen.getByTestId("page-1")).toBeDefined();
		expect(screen.getByTestId("page-2")).toBeDefined();
	});
});

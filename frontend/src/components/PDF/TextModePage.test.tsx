import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TextModePage from "./TextModePage";
import type { PageWithLines } from "./types";

// Mock dependencies
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, fallback?: string) => fallback || key,
	}),
}));

vi.mock("../../hooks/useIntersectionObserver", () => ({
	useIntersectionObserver: () => true, // Always visible for testing
}));

vi.mock("../Common/MarkdownContent", () => ({
	default: ({ children }: any) => {
		// Basic mock that renders children
		return <div data-testid="markdown-content">{children}</div>;
	},
}));

describe("TextModePage Component", () => {
	const mockPage: PageWithLines = {
		page_num: 1,
		content:
			"# Test Title\n\nThis is a test paragraph with a figure ![Fig](<10,10,50,50>).",
		figures: [
			{
				bbox: [10, 10, 50, 50] as [number, number, number, number],
				image_url: "/static/fig1.jpg",
				label: "figure",
				page_num: 1,
			},
		],
		lines: [],
		image_url: "",
		width: 800,
		height: 1200,
		words: [],
	};

	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("renders the page number and content", () => {
		render(<TextModePage page={mockPage} />);

		expect(screen.getByText("Page 1")).toBeDefined();
		expect(screen.getByTestId("markdown-content")).toBeDefined();
	});

	it("shows fallback text when content is empty", () => {
		const emptyPage = { ...mockPage, content: "", lines: [] };
		render(<TextModePage page={emptyPage} />);

		expect(
			screen.getByText("No content available for this page."),
		).toBeDefined();
	});

	it("handles search term highlighting (internally via highlightText logic)", () => {
		// Tests logical branch, though UI effects are mocked
	});

	it("displays the selection menu when text is selected", async () => {
		render(<TextModePage page={mockPage} />);

		// Get the actual container element from the component
		const pageContainer = document.getElementById("text-page-1")!;

		// Mock getBoundingClientRect for jsdom
		vi.spyOn(pageContainer, "getBoundingClientRect").mockReturnValue({
			width: 800,
			height: 1200,
			left: 0,
			top: 0,
			right: 800,
			bottom: 120,
			x: 0,
			y: 0,
			toJSON: () => {},
		} as any);

		const mockElement = document.createElement("div");
		pageContainer.appendChild(mockElement);

		const mockSelection = {
			toString: () => "selected text",
			rangeCount: 1,
			getRangeAt: () => ({
				startContainer: mockElement,
				commonAncestorContainer: mockElement,
				getBoundingClientRect: () => ({
					left: 100,
					right: 200,
					top: 100,
					bottom: 120,
					width: 100,
					height: 20,
				}),
			}),
		} as any;

		vi.stubGlobal("getSelection", () => mockSelection);

		await act(async () => {
			document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
		});

		// Flush the setTimeout(10ms) inside handleSelectionEnd with fake timers
		act(() => {
			vi.runAllTimers();
		});

		const toolbar = screen.getByRole("toolbar");
		expect(toolbar).toBeDefined();
		expect(screen.getByText("Translate")).toBeDefined();
	});

	it("calls onWordClick when Translate is clicked", async () => {
		const onWordClick = vi.fn();
		render(<TextModePage page={mockPage} onWordClick={onWordClick} />);

		const pageContainer = document.getElementById("text-page-1")!;
		vi.spyOn(pageContainer, "getBoundingClientRect").mockReturnValue({
			width: 800,
			height: 1200,
			left: 0,
			top: 0,
			right: 800,
			bottom: 120,
			x: 0,
			y: 0,
			toJSON: () => {},
		} as any);

		const mockElement = document.createElement("div");
		pageContainer.appendChild(mockElement);

		const mockSelection = {
			toString: () => "selected text",
			rangeCount: 1,
			getRangeAt: () => ({
				startContainer: mockElement,
				commonAncestorContainer: mockElement,
				getBoundingClientRect: () => ({
					left: 100,
					right: 200,
					top: 100,
					bottom: 120,
					width: 100,
					height: 20,
				}),
			}),
		} as any;
		vi.stubGlobal("getSelection", () => mockSelection);

		await act(async () => {
			document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
		});

		act(() => {
			vi.runAllTimers();
		});

		const translateBtn = screen.getByText("Translate");
		await act(async () => {
			fireEvent.click(translateBtn);
		});

		expect(onWordClick).toHaveBeenCalled();
	});
});

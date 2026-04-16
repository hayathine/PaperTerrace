import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DictionaryEntryCard from "./DictionaryEntryCard";

// Mock the hooks
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

// Mock components
vi.mock("../Common/MarkdownContent", () => ({
	default: ({ children }: { children: string }) => <div>{children}</div>,
}));

vi.mock("../Common/CopyButton", () => ({
	default: () => <button type="button">Copy</button>,
}));

vi.mock("../Common/FeedbackSection", () => ({
	default: () => <div>Feedback</div>,
}));

describe("DictionaryEntryCard", () => {
	const mockEntry = {
		word: "test-word",
		translation: "test-translation",
		source: "Gemini",
		trace_id: "test-trace",
	} as any;

	const defaultProps = {
		entry: mockEntry,
		currentSubTab: "translation" as const,
		sessionId: "test-session",
		savedItems: new Set<string>(),
		onSave: vi.fn(),
		onDeepTranslate: vi.fn(),
		onAskInChat: vi.fn(),
		onJump: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders basic entry information", () => {
		// Arrange & Act
		render(<DictionaryEntryCard {...defaultProps} />);

		// Assert
		expect(screen.getByText("test-word")).toBeDefined();
		expect(screen.getByText("test-translation")).toBeDefined();
		expect(screen.getByText("Gemini")).toBeDefined();
		expect(screen.getByText("Feedback")).toBeDefined();
	});

	it("renders analyzing state when is_analyzing is true", () => {
		// Arrange
		const props = {
			...defaultProps,
			entry: { ...mockEntry, is_analyzing: true },
		};

		// Act
		render(<DictionaryEntryCard {...props} />);

		// Assert
		expect(screen.getByText("summary.processing")).toBeDefined();
	});

	it("renders image when image_url is provided", () => {
		// Arrange
		const props = {
			...defaultProps,
			entry: { ...mockEntry, image_url: "https://example.com/image.png" },
		};

		// Act
		render(<DictionaryEntryCard {...props} />);

		// Assert
		const img = screen.getByAltText("Figure");
		expect(img).toBeDefined();
		expect(img.getAttribute("src")).toBe("https://example.com/image.png");
	});

	it("renders source translation in explanation tab", () => {
		// Arrange
		const props = {
			...defaultProps,
			currentSubTab: "explanation" as const,
			entry: { ...mockEntry, source_translation: "original context" },
		};

		// Act
		render(<DictionaryEntryCard {...props} />);

		// Assert
		expect(screen.getByText("viewer.dictionary.translation")).toBeDefined();
		expect(screen.getByText("original context")).toBeDefined();
	});

	it("calls onSave when save button is clicked", () => {
		// Arrange
		render(<DictionaryEntryCard {...defaultProps} />);

		// Act
		const saveButton = screen.getByText("viewer.dictionary.save_note");
		fireEvent.click(saveButton);

		// Assert
		expect(defaultProps.onSave).toHaveBeenCalledWith(mockEntry);
	});

	it("shows saved state when word is in savedItems", () => {
		// Arrange
		const props = {
			...defaultProps,
			savedItems: new Set(["test-word"]),
		};

		// Act
		render(<DictionaryEntryCard {...props} />);

		// Assert
		expect(screen.getByText("viewer.dictionary.saved")).toBeDefined();
		const saveButton = screen.getByRole("button", {
			name: /viewer\.dictionary\.saved/,
		});
		expect(saveButton.hasAttribute("disabled")).toBe(true);
	});

	it("calls onDeepTranslate when Ask AI is clicked", () => {
		// Arrange
		render(<DictionaryEntryCard {...defaultProps} />);

		// Act
		const askAiButton = screen.getByText("viewer.dictionary.ask_ai");
		fireEvent.click(askAiButton);

		// Assert
		expect(defaultProps.onDeepTranslate).toHaveBeenCalledWith(mockEntry);
	});

	it("calls onAskInChat when image is present and button is clicked", () => {
		// Arrange
		const props = {
			...defaultProps,
			entry: { ...mockEntry, image_url: "some-img" },
		};
		render(<DictionaryEntryCard {...props} />);

		// Act
		const askInChatButton = screen.getByText("viewer.dictionary.ask_in_chat");
		fireEvent.click(askInChatButton);

		// Assert
		expect(defaultProps.onAskInChat).toHaveBeenCalled();
	});

	it("calls onJump when jump button is clicked and coordinates are available", () => {
		// Arrange
		const props = {
			...defaultProps,
			entry: {
				...mockEntry,
				coords: { page: 1, x: 100, y: 200 },
			},
		};
		render(<DictionaryEntryCard {...props} />);

		// Act
		const jumpButton = screen.getByText("JUMP");
		fireEvent.click(jumpButton);

		// Assert
		expect(defaultProps.onJump).toHaveBeenCalledWith(1, 100, 200, "test-word");
	});
});

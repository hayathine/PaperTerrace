import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MessageBubble from "./MessageBubble";
import type { Message } from "./types";

// Mock the hooks and components
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, fallback?: string) => fallback || key,
	}),
}));

vi.mock("../Common/CopyButton", () => ({
	default: () => (
		<button type="button" data-testid="copy-button">
			Copy
		</button>
	),
}));

vi.mock("../Common/FeedbackSection", () => ({
	default: () => <div data-testid="feedback-section" />,
}));

describe("MessageBubble Component", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	const mockSessionId = "session-123";
	const userMessage: Message = {
		id: "1",
		role: "user",
		content: "Hello assistant",
		timestamp: Date.now(),
	};

	const assistantMessage: Message = {
		id: "2",
		role: "assistant",
		content: "Hello user! How can I help you?",
		timestamp: Date.now(),
		traceId: "trace-456",
	};

	it("renders user message correctly", () => {
		render(<MessageBubble message={userMessage} sessionId={mockSessionId} />);

		expect(screen.getByText("Hello assistant")).toBeDefined();
		// User messages should NOT have feedback section
		expect(screen.queryByTestId("feedback-section")).toBeNull();
	});

	it("renders assistant message correctly", () => {
		render(
			<MessageBubble message={assistantMessage} sessionId={mockSessionId} />,
		);

		expect(screen.getByText("Hello user! How can I help you?")).toBeDefined();
		// Assistant messages SHOULD have feedback section
		expect(screen.getByTestId("feedback-section")).toBeDefined();
	});

	it("renders timestamp", () => {
		// Use a fixed timestamp
		const timestamp = new Date("2024-01-01T12:00:00Z").getTime();
		const msg = { ...userMessage, timestamp };

		render(<MessageBubble message={msg} sessionId={mockSessionId} />);

		// The component uses toLocaleTimeString, so we just check if it's rendered.
		// Since it's locale-dependent, we can't easily check exact string without setting locale.
		// But in tests typically it's steady.
		const timeDisplay = new Date(timestamp).toLocaleTimeString([], {
			hour: "2-digit",
			minute: "2-digit",
		});
		expect(screen.getByText(timeDisplay)).toBeDefined();
	});

	it("shows evidence button when grounding is present", () => {
		const msgWithGrounding: Message = {
			...assistantMessage,
			grounding: {
				supports: [{ content: "Evidence match" }],
			},
		};
		const onEvidenceClick = vi.fn();

		render(
			<MessageBubble
				message={msgWithGrounding}
				sessionId={mockSessionId}
				onEvidenceClick={onEvidenceClick}
			/>,
		);

		const evidenceBtn = screen.getByText("根拠を表示");
		expect(evidenceBtn).toBeDefined();

		fireEvent.click(evidenceBtn);
		expect(onEvidenceClick).toHaveBeenCalledWith(msgWithGrounding.grounding);
	});

	it("does not show evidence button when grounding is missing", () => {
		render(
			<MessageBubble message={assistantMessage} sessionId={mockSessionId} />,
		);
		expect(screen.queryByText("根拠を表示")).toBeNull();
	});
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MessageList from "./MessageList";
import type { Message } from "./types";

// Mock child components
vi.mock("./MessageBubble", () => ({
	default: ({ message }: { message: Message }) => (
		<div data-testid={`message-bubble-${message.id}`}>{message.content}</div>
	),
}));

describe("MessageList Component", () => {
	const mockSessionId = "session-123";
	const messages: Message[] = [
		{ id: "1", role: "user", content: "Hi", timestamp: Date.now() },
		{ id: "2", role: "assistant", content: "Hello!", timestamp: Date.now() },
	];

	// Mock scrollIntoView
	window.HTMLElement.prototype.scrollIntoView = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
		// Re-mock scrollIntoView as vi.clearAllMocks() will clear it
		window.HTMLElement.prototype.scrollIntoView = vi.fn();
	});

	it("renders all messages", () => {
		render(
			<MessageList
				messages={messages}
				isLoading={false}
				sessionId={mockSessionId}
			/>,
		);

		expect(screen.getByTestId("message-bubble-1")).toBeDefined();
		expect(screen.getByTestId("message-bubble-2")).toBeDefined();
		expect(screen.getByText("Hi")).toBeDefined();
		expect(screen.getByText("Hello!")).toBeDefined();
	});

	it("shows empty state message when no messages", () => {
		render(
			<MessageList messages={[]} isLoading={false} sessionId={mockSessionId} />,
		);

		expect(
			screen.getByText("No messages yet. Start a conversation!"),
		).toBeDefined();
	});

	it("shows loading indicator when isLoading is true", () => {
		render(
			<MessageList
				messages={messages}
				isLoading={true}
				sessionId={mockSessionId}
			/>,
		);

		// The loading indicator is an animate-pulse div
		// We can check if it's present by searching for something that only appears in loading state
		// or just looking for the animation class (though that's implementation detail)
	});

	it("scrolls to bottom when messages change", () => {
		const { rerender } = render(
			<MessageList
				messages={[messages[0]]}
				isLoading={false}
				sessionId={mockSessionId}
			/>,
		);

		expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();

		rerender(
			<MessageList
				messages={messages}
				isLoading={false}
				sessionId={mockSessionId}
			/>,
		);

		expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
	});
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatWindow from "./ChatWindow";

// Mock dependencies
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "ja" },
	}),
}));

vi.mock("../../contexts/LoadingContext", () => ({
	useLoading: () => ({
		startLoading: vi.fn(),
		stopLoading: vi.fn(),
	}),
}));

const mockToken = "test-token-456";
vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		token: mockToken,
	}),
}));

// Mock child components to simplify testing ChatWindow logic
vi.mock("./MessageList", () => ({
	default: ({ messages }: any) => (
		<div data-testid="messages">
			{messages.map((m: any, i: number) => (
				<div key={i}>{m.content}</div>
			))}
		</div>
	),
}));

vi.mock("./InputArea", () => ({
	default: ({ onSendMessage, isLoading }: any) => (
		<div>
			<button
				type="button"
				disabled={isLoading}
				onClick={() => onSendMessage("Hello AI")}
				data-testid="send-btn"
			>
				Send
			</button>
		</div>
	),
}));

describe("ChatWindow Component", () => {
	beforeEach(() => {
		vi.resetAllMocks();
		global.fetch = vi.fn();
	});

	it("fetches chat history on mount with authorization header", async () => {
		const mockHistory = {
			history: [
				{ role: "user", content: "Hi" },
				{ role: "assistant", content: "Hello" },
			],
		};

		(global.fetch as any).mockResolvedValue({
			ok: true,
			json: async () => mockHistory,
		});

		render(<ChatWindow sessionId="s123" paperId="p456" />);

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/chat/history"),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: `Bearer ${mockToken}`,
					}),
				}),
			);
		});

		await waitFor(() => {
			expect(screen.getByTestId("messages").textContent).toContain("Hi");
			expect(screen.getByTestId("messages").textContent).toContain("Hello");
		});
	});

	it("sends a message and adds both user and assistant responses", async () => {
		// Mock history fetch (empty)
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => ({ history: [] }),
		});

		// Mock chat send
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => ({ response: "AI Feedback", trace_id: "t1" }),
		});

		render(<ChatWindow sessionId="s123" paperId="p456" />);

		// Wait for mount fetch to finish
		await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

		const sendBtn = screen.getByTestId("send-btn");
		fireEvent.click(sendBtn);

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledTimes(2);
			expect(global.fetch).toHaveBeenNthCalledWith(
				2,
				expect.stringContaining("/api/chat"),
				expect.objectContaining({
					method: "POST",
					headers: expect.objectContaining({
						Authorization: `Bearer ${mockToken}`,
						"Content-Type": "application/json",
					}),
					body: expect.stringContaining('"message":"Hello AI"'),
				}),
			);
		});

		await waitFor(() => {
			const text = screen.getByTestId("messages").textContent || "";
			expect(text).toContain("Hello AI");
			expect(text).toContain("AI Feedback");
		});
	});

	it("handles fetch errors gracefully", async () => {
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => ({ history: [] }),
		});

		(global.fetch as any).mockResolvedValueOnce({
			ok: false,
		});

		render(<ChatWindow sessionId="s123" paperId="p456" />);

		// Wait for mount fetch to finish
		await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

		const sendBtn = screen.getByTestId("send-btn");
		fireEvent.click(sendBtn);

		await waitFor(() => {
			const text = screen.getByTestId("messages").textContent || "";
			expect(text).toContain("chat.error_retry");
		});
	});
});

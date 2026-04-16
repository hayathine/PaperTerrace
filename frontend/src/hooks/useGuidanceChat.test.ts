import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGuidanceChat } from "./useGuidanceChat";

describe("useGuidanceChat Hook", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();

		// Ensure crypto.randomUUID is a mock
		if (!global.crypto) {
			global.crypto = {
				randomUUID: vi.fn(
					() =>
						"00000000-0000-0000-0000-000000000000" as `${string}-${string}-${string}-${string}-${string}`,
				),
			} as any;
		} else {
			vi.spyOn(global.crypto, "randomUUID").mockReturnValue(
				"00000000-0000-0000-0000-000000000000" as `${string}-${string}-${string}-${string}-${string}`,
			);
		}
	});

	it("should initialize with empty messages", () => {
		const { result } = renderHook(() => useGuidanceChat());
		expect(result.current.messages).toEqual([]);
		expect(result.current.isLoading).toBe(false);
	});

	it("should handle streaming chat response", async () => {
		const mockChunks = [
			'data: {"type": "chunk", "content": "Hello"}\n',
			'data: {"type": "chunk", "content": " world"}\n',
			'data: {"type": "done", "conversation_id": "new-conv-id"}\n',
		];

		const stream = new ReadableStream({
			start(controller) {
				for (const chunk of mockChunks) {
					controller.enqueue(new TextEncoder().encode(chunk));
				}
				controller.close();
			},
		});

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			body: stream,
		});

		const { result } = renderHook(() => useGuidanceChat());

		await act(async () => {
			await result.current.sendMessage("Hi", { route: "/test" });
		});

		// Wait for the stream to process
		await waitFor(() => {
			expect(result.current.messages).toHaveLength(2);
			expect(result.current.messages[0]).toEqual({
				role: "user",
				content: "Hi",
			});
			expect(result.current.messages[1]).toEqual({
				role: "assistant",
				content: "Hello world",
			});
			expect(result.current.isLoading).toBe(false);
		});
	});

	it("should handle partial JSON chunks in stream", async () => {
		const mockChunks = [
			'data: {"type": "chunk", "cont',
			'ent": "Hello"}\n',
			'data: {"type": "done", "conversation_id": "conv-123"}\n',
		];

		const stream = new ReadableStream({
			start(controller) {
				for (const chunk of mockChunks) {
					controller.enqueue(new TextEncoder().encode(chunk));
				}
				controller.close();
			},
		});

		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			body: stream,
		});

		const { result } = renderHook(() => useGuidanceChat());

		await act(async () => {
			await result.current.sendMessage("Hi", { route: "/test" });
		});

		await waitFor(() => {
			expect(result.current.messages[1].content).toBe("Hello");
		});
	});

	it("should handle fetch errors", async () => {
		(global.fetch as any).mockResolvedValueOnce({
			ok: false,
			status: 500,
		});

		const { result } = renderHook(() => useGuidanceChat());

		await act(async () => {
			await result.current.sendMessage("Hi", { route: "/test" });
		});

		await waitFor(() => {
			expect(result.current.messages[1].content).toContain(
				"申し訳ありません、応答の取得に失敗しました",
			);
			expect(result.current.isLoading).toBe(false);
		});
	});

	it("should clear messages and reset conversation ID", () => {
		const { result } = renderHook(() => useGuidanceChat());

		act(() => {
			result.current.clearMessages();
		});

		expect(result.current.messages).toEqual([]);
		expect(global.crypto.randomUUID).toHaveBeenCalled();
	});
});

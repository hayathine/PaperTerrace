import { useCallback, useRef, useState } from "react";

// 開発環境: Vite プロキシ経由 (/api/guidance → localhost:8090)
// 本番環境: Cloudflare Workers 経由で guidance サービスへルーティング
const GUIDANCE_BASE = "/api/guidance";

export interface GuidanceMessage {
	role: "user" | "assistant";
	content: string;
}

interface PageContext {
	route: string;
	page_title?: string;
}

export function useGuidanceChat() {
	const [messages, setMessages] = useState<GuidanceMessage[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const conversationIdRef = useRef<string>(crypto.randomUUID());

	const sendMessage = useCallback(
		async (text: string, context: PageContext) => {
			if (!text.trim() || isLoading) return;

			const userMessage: GuidanceMessage = { role: "user", content: text };
			setMessages((prev) => [...prev, userMessage]);
			setIsLoading(true);

			// AI メッセージのプレースホルダーを追加
			setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

			try {
				const response = await fetch(`${GUIDANCE_BASE}/chat`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Accept: "text/event-stream",
					},
					body: JSON.stringify({
						message: text,
						conversation_id: conversationIdRef.current,
						context: {
							route: context.route,
							page_title: context.page_title,
						},
					}),
				});

				if (!response.ok) {
					throw new Error(`HTTP ${response.status}`);
				}

				const reader = response.body?.getReader();
				const decoder = new TextDecoder();
				let buffer = "";

				if (!reader) throw new Error("No response body");

				while (true) {
					const { done, value } = await reader.read();
					if (done) break;

					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split("\n");
					buffer = lines.pop() ?? "";

					for (const line of lines) {
						if (!line.startsWith("data: ")) continue;
						const jsonStr = line.slice(6).trim();
						if (!jsonStr) continue;

						try {
							const event = JSON.parse(jsonStr) as {
								type: "chunk" | "done" | "error";
								content?: string;
								conversation_id?: string;
							};

							if (event.type === "chunk" && event.content) {
								setMessages((prev) => {
									const updated = [...prev];
									const last = updated[updated.length - 1];
									if (last?.role === "assistant") {
										updated[updated.length - 1] = {
											...last,
											content: last.content + event.content,
										};
									}
									return updated;
								});
							} else if (event.type === "done" && event.conversation_id) {
								conversationIdRef.current = event.conversation_id;
							} else if (event.type === "error") {
								throw new Error(event.content ?? "Unknown error");
							}
						} catch {
							// JSON パースエラーは無視
						}
					}
				}
			} catch (_err) {
				setMessages((prev) => {
					const updated = [...prev];
					const last = updated[updated.length - 1];
					if (last?.role === "assistant" && last.content === "") {
						updated[updated.length - 1] = {
							...last,
							content:
								"申し訳ありません、応答の取得に失敗しました。しばらくしてから再試行してください。",
						};
					}
					return updated;
				});
			} finally {
				setIsLoading(false);
			}
		},
		[isLoading, messages.length],
	);

	const clearMessages = useCallback(() => {
		setMessages([]);
		conversationIdRef.current = crypto.randomUUID();
	}, []);

	return { messages, isLoading, sendMessage, clearMessages };
}

import type React from "react";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
	type GuidanceMessage,
	useGuidanceChat,
} from "../../hooks/useGuidanceChat";
import MarkdownContent from "../Common/MarkdownContent";

const WELCOME_MESSAGE: GuidanceMessage = {
	role: "assistant",
	content:
		"PaperTerrace の使い方についてお気軽にご質問ください！\n\n例えば「翻訳はどうやるの？」「AI に質問するには？」などお聞きいただけます。",
};

export default function HelpAssistant() {
	const [isOpen, setIsOpen] = useState(false);
	const [inputText, setInputText] = useState("");
	const { messages, isLoading, sendMessage, clearMessages } = useGuidanceChat();
	const messagesEndRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLTextAreaElement>(null);
	const location = useLocation();

	// メッセージ追加時に自動スクロール
	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	// パネルを開いたらテキストエリアにフォーカス
	useEffect(() => {
		if (isOpen) {
			setTimeout(() => inputRef.current?.focus(), 100);
		}
	}, [isOpen]);

	const handleSend = async () => {
		const text = inputText.trim();
		if (!text || isLoading) return;
		setInputText("");
		await sendMessage(text, {
			route: location.pathname,
			page_title: document.title,
		});
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	};

	const handleClose = () => {
		setIsOpen(false);
	};

	const handleClear = () => {
		clearMessages();
	};

	const allMessages = messages.length === 0 ? [WELCOME_MESSAGE] : messages;

	return (
		<div className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-3">
			{/* チャットパネル */}
			{isOpen && (
				<div
					className="flex flex-col bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden"
					style={{ width: "360px", height: "480px" }}
				>
					{/* ヘッダー */}
					<div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-orange-500 to-amber-500 text-white flex-shrink-0">
						<div className="flex items-center gap-2">
							<svg
								className="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								aria-hidden="true"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth={2}
									d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
								/>
							</svg>
							<span className="font-semibold text-sm">使い方ガイド</span>
						</div>
						<div className="flex items-center gap-1">
							{messages.length > 0 && (
								<button
									type="button"
									onClick={handleClear}
									className="p-1.5 rounded-lg hover:bg-white/20 transition-colors text-white/80 hover:text-white"
									title="会話をリセット"
								>
									<svg
										className="w-4 h-4"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										aria-hidden="true"
									>
										<path
											strokeLinecap="round"
											strokeLinejoin="round"
											strokeWidth={2}
											d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
										/>
									</svg>
								</button>
							)}
							<button
								type="button"
								onClick={handleClose}
								className="p-1.5 rounded-lg hover:bg-white/20 transition-colors text-white/80 hover:text-white"
								aria-label="閉じる"
							>
								<svg
									className="w-4 h-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									aria-hidden="true"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={2}
										d="M6 18L18 6M6 6l12 12"
									/>
								</svg>
							</button>
						</div>
					</div>

					{/* メッセージ一覧 */}
					<div className="flex-1 overflow-y-auto p-3 space-y-3">
						{allMessages.map((msg, i) => (
							<MessageBubble key={`${msg.role}-${i}`} message={msg} />
						))}
						{isLoading && (
							<div className="flex justify-start">
								<div className="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-2">
									<ThinkingDots />
								</div>
							</div>
						)}
						<div ref={messagesEndRef} />
					</div>

					{/* 入力エリア */}
					<div className="flex-shrink-0 border-t border-gray-100 p-3">
						<div className="flex items-end gap-2 bg-gray-50 rounded-xl px-3 py-2 border border-gray-200 focus-within:border-orange-400 transition-colors">
							<textarea
								ref={inputRef}
								value={inputText}
								onChange={(e) => setInputText(e.target.value)}
								onKeyDown={handleKeyDown}
								placeholder="機能について質問してください..."
								rows={1}
								className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none outline-none leading-5"
								style={{ maxHeight: "80px" }}
								disabled={isLoading}
							/>
							<button
								type="button"
								onClick={handleSend}
								disabled={!inputText.trim() || isLoading}
								className="flex-shrink-0 p-1.5 rounded-lg bg-orange-500 text-white disabled:opacity-40 hover:bg-orange-600 transition-colors"
								aria-label="送信"
							>
								<svg
									className="w-4 h-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									aria-hidden="true"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={2}
										d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
									/>
								</svg>
							</button>
						</div>
						<p className="text-xs text-gray-400 mt-1.5 text-center">
							Enter で送信 / Shift+Enter で改行
						</p>
					</div>
				</div>
			)}

			{/* フローティングボタン */}
			<button
				type="button"
				onClick={() => setIsOpen((prev) => !prev)}
				className="flex items-center justify-center w-12 h-12 rounded-full shadow-lg bg-gradient-to-br from-orange-500 to-amber-500 text-white hover:from-orange-600 hover:to-amber-600 transition-all duration-200 hover:scale-105 active:scale-95"
				aria-label={isOpen ? "ガイドを閉じる" : "使い方ガイドを開く"}
			>
				{isOpen ? (
					<svg
						className="w-5 h-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						aria-hidden="true"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2.5}
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				) : (
					<svg
						className="w-6 h-6"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						aria-hidden="true"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2}
							d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				)}
			</button>
		</div>
	);
}

function MessageBubble({ message }: { message: GuidanceMessage }) {
	const isUser = message.role === "user";

	if (isUser) {
		return (
			<div className="flex justify-end">
				<div className="max-w-[80%] bg-orange-500 text-white rounded-2xl rounded-tr-none px-3 py-2 text-sm leading-relaxed">
					{message.content}
				</div>
			</div>
		);
	}

	return (
		<div className="flex justify-start">
			<div className="max-w-[85%] bg-gray-100 rounded-2xl rounded-tl-none px-3 py-2">
				<MarkdownContent className="text-sm text-gray-800 leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-headings:my-1 prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1">
					{message.content || ""}
				</MarkdownContent>
			</div>
		</div>
	);
}

function ThinkingDots() {
	return (
		<div className="flex items-center gap-1 py-0.5">
			{[0, 1, 2].map((i) => (
				<span
					key={i}
					className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
					style={{ animationDelay: `${i * 0.15}s` }}
				/>
			))}
		</div>
	);
}

import type React from "react";
import { useTranslation } from "react-i18next";
import type { Message } from "./types";

interface MessageBubbleProps {
	message: Message;
	onStackPaper?: (url: string, title?: string) => void;
	onEvidenceClick?: (grounding: any) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
	message,
	onStackPaper,
	onEvidenceClick,
}) => {
	const { t } = useTranslation();
	const isUser = message.role === "user";
	const hasGrounding =
		message.grounding &&
		(message.grounding.supports?.length > 0 ||
			message.grounding.chunks?.length > 0);

	const renderContent = (content: string) => {
		// Regex for Markdown links [text](url), raw URLs (http/https/www/protocol-relative), and DOIs
		const urlRegex =
			/(\[([^\]]+)\]\(((?:https?:\/\/|\/\/)[^\s)]+)\))|((?:https?:\/\/|\/\/)[^\s\n]+|www\.[^\s\n]+)|(10\.\d{4,9}\/[-._();/:A-Z0-9]+)/gi;

		const elements: React.ReactNode[] = [];
		let lastIndex = 0;
		let match = urlRegex.exec(content);
		while (match !== null) {
			// Add text before the match
			if (match.index > lastIndex) {
				elements.push(content.substring(lastIndex, match.index));
			}

			const markdownLabel = match[2];
			const markdownUrl = match[3];
			const rawUrl = match[4];
			const doi = match[5];

			let targetUrl = "";
			let labelText = "";

			if (markdownUrl) {
				targetUrl = markdownUrl;
				labelText = markdownLabel;
			} else if (rawUrl) {
				targetUrl = rawUrl.startsWith("www.") ? `https://${rawUrl}` : rawUrl;
				labelText = rawUrl;
			} else if (doi) {
				targetUrl = `https://doi.org/${doi}`;
				labelText = doi;
			}

			// Sanitize: separate trailing punctuation from the URL/Label
			const punctuationMatch = targetUrl.match(/([.,!?;:)]+)$/);
			const trailingPunctuation = punctuationMatch ? punctuationMatch[0] : "";
			const cleanUrl = targetUrl.substring(
				0,
				targetUrl.length - trailingPunctuation.length,
			);
			const cleanLabel = labelText.substring(
				0,
				labelText.length - trailingPunctuation.length,
			);

			elements.push(
				<button
					type="button"
					key={match.index}
					onClick={(e) => {
						e.preventDefault();
						if (onStackPaper) {
							onStackPaper(cleanUrl);
						}
						window.open(cleanUrl, "_blank", "noopener,noreferrer");
					}}
					className="text-blue-600 hover:text-blue-800 underline break-all inline-flex items-center gap-0.5 group/link text-left font-semibold"
					title={`Stack this paper: ${cleanUrl}`}
				>
					{cleanLabel}
					<svg
						className="w-3 h-3 min-w-[12px] opacity-0 group-hover/link:opacity-100 transition-opacity"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2.5}
							d="M12 6v6m0 0v6m0-6h6m-6 0H6"
						/>
					</svg>
				</button>,
			);

			if (trailingPunctuation) {
				elements.push(trailingPunctuation);
			}

			lastIndex = urlRegex.lastIndex;
			match = urlRegex.exec(content);
		}

		// Add remaining text
		if (lastIndex < content.length) {
			elements.push(content.substring(lastIndex));
		}

		return elements;
	};

	return (
		<div
			className={`flex w-full mb-4 ${isUser ? "justify-end" : "justify-start"}`}
		>
			<div
				className={`max-w-[85%] rounded border px-3 py-2 ${
					isUser
						? "bg-slate-800 text-white border-slate-900"
						: "bg-white text-slate-800 border-slate-200 shadow-sm"
				}`}
			>
				<div className="whitespace-pre-wrap text-sm leading-relaxed font-medium">
					{renderContent(message.content)}
				</div>

				{hasGrounding && onEvidenceClick && (
					<div className="mt-3 pt-2 border-t border-slate-100 flex justify-end">
						<button
							type="button"
							onClick={() => onEvidenceClick(message.grounding)}
							className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 transition-colors flex items-center gap-1 group/ev"
						>
							<svg
								className="w-3 h-3 group-hover/ev:scale-110 transition-transform"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth={2}
									d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
								/>
							</svg>
							{t("chat.show_evidence", "根拠を表示")}
						</button>
					</div>
				)}

				<div
					className={`text-[9px] font-bold uppercase tracking-widest mt-1.5 opacity-50 ${isUser ? "text-right" : "text-left"}`}
				>
					{new Date(message.timestamp).toLocaleTimeString([], {
						hour: "2-digit",
						minute: "2-digit",
					})}
				</div>
			</div>
		</div>
	);
};

export default MessageBubble;

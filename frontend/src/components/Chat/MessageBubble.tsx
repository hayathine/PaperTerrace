import type React from "react";
import { useTranslation } from "react-i18next";
import CopyButton from "../Common/CopyButton";
import MarkdownContent from "../Common/MarkdownContent";
import ChatFeedback from "./ChatFeedback";
import type { Message } from "./types";

interface MessageBubbleProps {
	message: Message;
	sessionId: string;
	onEvidenceClick?: (grounding: any) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
	message,
	sessionId,
	onEvidenceClick,
}) => {
	const { t } = useTranslation();
	const isUser = message.role === "user";
	const hasGrounding =
		message.grounding &&
		(message.grounding.supports?.length > 0 ||
			message.grounding.chunks?.length > 0);

	return (
		<div
			className={`flex flex-col w-full mb-4 ${isUser ? "items-end" : "items-start"} group/row`}
		>
			<div
				className={`max-w-[92%] sm:max-w-[85%] rounded border px-3 py-2 group/msg relative ${
					isUser
						? "bg-orange-600 text-white border-orange-700 shadow-md shadow-orange-100"
						: "bg-white text-slate-800 border-slate-200 shadow-sm"
				}`}
			>
				<div className="absolute top-1 right-1 opacity-0 group-hover/msg:opacity-100 transition-opacity">
					<CopyButton
						text={message.content}
						size={12}
						className={
							isUser
								? "text-orange-50 hover:text-white hover:bg-orange-500"
								: ""
						}
					/>
				</div>
				<MarkdownContent
					className={`prose prose-sm max-w-none text-sm leading-relaxed font-medium ${isUser ? "prose-invert" : ""}`}
					components={{
						a: ({ href, children: linkChildren }) => (
							<button
								type="button"
								onClick={(e) => {
									e.preventDefault();
									if (href) {
										window.open(href, "_blank", "noopener,noreferrer");
									}
								}}
								className="text-blue-600 hover:text-blue-800 underline break-all inline-flex items-center gap-0.5 group/link text-left font-semibold"
								title={href ? `Open: ${href}` : undefined}
							>
								{linkChildren}
							</button>
						),
					}}
				>
					{message.content}
				</MarkdownContent>

				{hasGrounding && onEvidenceClick && (
					<div className="mt-3 pt-2 border-t border-slate-100 flex justify-end">
						<button
							type="button"
							onClick={() => onEvidenceClick(message.grounding)}
							className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 bg-orange-50 text-orange-600 rounded hover:bg-orange-100 transition-colors flex items-center gap-1 group/ev"
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
					className={`text-[10px] font-bold uppercase tracking-widest mt-1.5 opacity-50 ${isUser ? "text-right" : "text-left"}`}
				>
					{new Date(message.timestamp).toLocaleTimeString([], {
						hour: "2-digit",
						minute: "2-digit",
					})}
				</div>
			</div>
			{!isUser && (
				<div className="opacity-0 group-hover/row:opacity-100 transition-opacity duration-150">
					<ChatFeedback sessionId={sessionId} messageId={message.id} />
				</div>
			)}
		</div>
	);
};

export default MessageBubble;

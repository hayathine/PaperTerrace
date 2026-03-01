import type React from "react";
import { useState } from "react";
import { submitFeedback } from "@/lib/feedback";

interface ChatFeedbackProps {
	sessionId: string;
	messageId: string;
}

/**
 * Icon-only thumbs up/down feedback for individual assistant messages.
 * Submits immediately on click without requiring a comment.
 */
const ChatFeedback: React.FC<ChatFeedbackProps> = ({
	sessionId,
	messageId,
}) => {
	const [score, setScore] = useState<number | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const handleClick = async (newScore: number) => {
		if (isSubmitting || score === newScore) return;
		setScore(newScore);
		setIsSubmitting(true);
		try {
			await submitFeedback({
				session_id: sessionId,
				target_type: "chat",
				target_id: messageId,
				user_score: newScore,
			});
		} catch (e) {
			console.error("Chat feedback error:", e);
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="flex gap-2 sm:gap-0.5 mt-0.5 ml-0.5">
			<button
				type="button"
				onClick={() => handleClick(1)}
				disabled={isSubmitting}
				aria-label="Good"
				className={`p-2.5 sm:p-1 rounded transition-all duration-200 ${
					score === 1
						? "text-emerald-500"
						: "text-slate-300 hover:text-slate-500"
				}`}
			>
				<svg
					className="w-4 h-4 sm:w-3.5 sm:h-3.5"
					viewBox="0 0 24 24"
					fill={score === 1 ? "currentColor" : "none"}
					stroke="currentColor"
					strokeWidth={1.5}
					aria-hidden="true"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						d="M6.633 10.25c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 0 1 2.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 0 0 .322-1.672V2.75a.75.75 0 0 1 .75-.75 2.25 2.25 0 0 1 2.25 2.25c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282m0 0h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 0 1-2.649 7.521c-.388.482-.987.729-1.605.729H13.48c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 0 0-1.423-.23H5.904m10.598-9.75H14.25M5.904 18.5c.083.205.173.405.27.602.197.4-.078.898-.523.898h-.908c-.889 0-1.713-.518-1.972-1.368a12 12 0 0 1-.521-3.507c0-1.553.295-3.036.831-4.398C3.387 9.953 4.167 9.5 5 9.5h1.053c.472 0 .745.556.5.96a8.958 8.958 0 0 0-1.302 4.665c0 1.194.232 2.333.654 3.375Z"
					/>
				</svg>
			</button>
			<button
				type="button"
				onClick={() => handleClick(0)}
				disabled={isSubmitting}
				aria-label="Bad"
				className={`p-2.5 sm:p-1 rounded transition-all duration-200 ${
					score === 0 ? "text-rose-400" : "text-slate-300 hover:text-slate-500"
				}`}
			>
				<svg
					className="w-3.5 h-3.5"
					viewBox="0 0 24 24"
					fill={score === 0 ? "currentColor" : "none"}
					stroke="currentColor"
					strokeWidth={1.5}
					aria-hidden="true"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						d="M7.498 15.25H4.372c-1.026 0-1.945-.694-2.054-1.715a12.137 12.137 0 0 1-.068-1.285c0-2.848.992-5.464 2.649-7.521C5.287 4.247 5.886 4 6.504 4h4.016a4.5 4.5 0 0 1 1.423.23l3.114 1.04a4.5 4.5 0 0 0 1.423.23h1.294M7.498 15.25c.618 0 .991.724.725 1.282A7.471 7.471 0 0 0 7.5 19.75 2.25 2.25 0 0 0 9.75 22a.75.75 0 0 0 .75-.75v-.633c0-.573.11-1.14.322-1.672.304-.76.93-1.33 1.653-1.715a9.04 9.04 0 0 0 2.86-2.4c.498-.634 1.226-1.08 2.032-1.08h.384m-10.253 1.5H9.7m8.075-9.75c.03.22.048.444.048.673 0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.952 11.952 0 0 1-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 0 0-1.423-.23h-.5"
					/>
				</svg>
			</button>
		</div>
	);
};

export default ChatFeedback;

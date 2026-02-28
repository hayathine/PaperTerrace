import type React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { submitFeedback } from "@/lib/feedback";

interface FeedbackSectionProps {
	sessionId: string;
	targetType:
		| "recommendation"
		| "summary"
		| "critique"
		| "related_papers"
		| "chat"
		| "translation";
	targetId?: string;
}

const FeedbackSection: React.FC<FeedbackSectionProps> = ({
	sessionId,
	targetType,
	targetId,
}) => {
	const { t } = useTranslation();
	const [status, setStatus] = useState<
		"idle" | "submitting" | "submitted" | "error"
	>("idle");
	const [score, setScore] = useState<number | null>(null);
	const [comment, setComment] = useState("");

	const handleSubmit = async (e?: React.FormEvent) => {
		if (e) e.preventDefault();
		if (score === null) return;

		setStatus("submitting");
		try {
			await submitFeedback({
				session_id: sessionId,
				target_type: targetType,
				target_id: targetId,
				user_score: score,
				user_comment: comment.trim() || undefined,
			});
			setStatus("submitted");
		} catch (error) {
			console.error("Feedback error:", error);
			setStatus("error");
		}
	};

	if (status === "submitted") {
		return (
			<div className="flex items-center gap-2 py-4 px-3 bg-emerald-50/50 border border-emerald-100/50 rounded-xl animate-in fade-in zoom-in-95 duration-300 mt-4">
				<div className="w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center shadow-lg shadow-emerald-500/20">
					<svg
						className="w-3.5 h-3.5 text-white"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="3"
							d="M5 13l4 4L19 7"
						/>
					</svg>
				</div>
				<span className="text-xs font-bold text-emerald-700">
					{t("common.feedback.submitted")}
				</span>
			</div>
		);
	}

	return (
		<div className="space-y-4 py-5 border-t border-slate-100 mt-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
			<div className="flex items-center justify-between">
				<span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
					{t("common.feedback.title")}
				</span>
				<div className="flex gap-2">
					<button
						type="button"
						disabled={status === "submitting"}
						onClick={() => setScore(1)}
						className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 ${
							score === 1
								? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30 scale-105"
								: "bg-slate-50 text-slate-500 hover:bg-emerald-50 hover:text-emerald-600"
						}`}
					>
						<span className={`${score === 1 ? "animate-bounce" : ""}`}>👍</span>
						{t("common.feedback.good")}
					</button>
					<button
						type="button"
						disabled={status === "submitting"}
						onClick={() => setScore(0)}
						className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-300 ${
							score === 0
								? "bg-rose-500 text-white shadow-lg shadow-rose-500/30 scale-105"
								: "bg-slate-50 text-slate-500 hover:bg-rose-50 hover:text-rose-600"
						}`}
					>
						<span className={`${score === 0 ? "animate-bounce" : ""}`}>👎</span>
						{t("common.feedback.bad")}
					</button>
				</div>
			</div>

			<div
				className={`space-y-3 transition-all duration-500 overflow-hidden ${
					score !== null
						? "max-h-[300px] opacity-100"
						: "max-h-0 opacity-0 pointer-events-none"
				}`}
			>
				<textarea
					value={comment}
					onChange={(e) => setComment(e.target.value)}
					placeholder={t("common.feedback.placeholder")}
					className="w-full min-h-[80px] p-3 text-xs bg-slate-50 border border-slate-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-slate-200 transition-all resize-none"
				/>
				<div className="flex justify-end">
					<button
						type="button"
						disabled={status === "submitting" || score === null}
						onClick={() => handleSubmit()}
						className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 text-white text-xs font-bold rounded-lg transition-all shadow-md active:scale-95 disabled:active:scale-100"
					>
						{status === "submitting" ? (
							<div className="flex items-center gap-2">
								<div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
								<span>{t("common.loading")}</span>
							</div>
						) : (
							<span>{t("common.feedback.send")}</span>
						)}
					</button>
				</div>
			</div>

			{status === "error" && (
				<p className="text-[10px] text-rose-500 animate-pulse">
					{t("common.error.generic")}
				</p>
			)}
		</div>
	);
};

export default FeedbackSection;

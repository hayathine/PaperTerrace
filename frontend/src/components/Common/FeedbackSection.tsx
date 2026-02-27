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
		| "chat";
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
	const [comment] = useState("");

	const handleSubmit = async (selectedScore: number) => {
		setScore(selectedScore); // Set the score immediately when a button is clicked
		setStatus("submitting");
		try {
			await submitFeedback({
				session_id: sessionId,
				target_type: targetType,
				target_id: targetId,
				user_score: selectedScore,
				user_comment: comment || undefined,
			});
			setStatus("submitted");
		} catch (error) {
			console.error("Feedback error:", error);
			setStatus("error");
		}
	};

	if (status === "submitted") {
		return (
			<div className="flex items-center gap-2 py-2 px-3 bg-green-50 border border-green-100 rounded-lg animate-in fade-in duration-300">
				<div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
					<svg
						className="w-3 h-3 text-white"
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
				<span className="text-[10px] font-bold text-green-700">
					{t("common.feedback.submitted")}
				</span>
			</div>
		);
	}

	return (
		<div className="space-y-3 py-4 border-t border-slate-100 mt-4">
			<div className="flex items-center justify-between">
				<span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
					{t("common.feedback.title")}
				</span>
				<div className="flex gap-2">
					<button
						type="button"
						disabled={status === "submitting"}
						onClick={() => handleSubmit(1)}
						className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
							score === 1
								? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30"
								: "bg-slate-50 text-slate-500 hover:bg-emerald-50 hover:text-emerald-600"
						}`}
					>
						<span>👍</span>
						{t("common.feedback.good")}
					</button>
					<button
						type="button"
						disabled={status === "submitting"}
						onClick={() => handleSubmit(0)}
						className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
							score === 0
								? "bg-rose-500 text-white shadow-lg shadow-rose-500/30"
								: "bg-slate-50 text-slate-500 hover:bg-rose-50 hover:text-rose-600"
						}`}
					>
						<span>👎</span>
						{t("common.feedback.bad")}
					</button>
				</div>
			</div>

			{status === "error" && (
				<p className="text-[10px] text-rose-500">{t("common.error.generic")}</p>
			)}
		</div>
	);
};

export default FeedbackSection;

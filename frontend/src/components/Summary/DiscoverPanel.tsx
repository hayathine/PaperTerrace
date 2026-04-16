import React from "react";
import { useTranslation } from "react-i18next";
import { createLogger } from "@/lib/logger";
import {
	generateRecommendations,
	type RecommendationGenerateResponse,
} from "@/lib/recommendation";
import { useAuth } from "../../contexts/AuthContext";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";

const log = createLogger("DiscoverPanel");

interface DiscoverPanelProps {
	sessionId: string;
}

const DiscoverPanel: React.FC<DiscoverPanelProps> = ({ sessionId }) => {
	const { t } = useTranslation();
	const { token } = useAuth();

	const [userQuery, setUserQuery] = React.useState("");
	const [recommendationOpen, setRecommendationOpen] = React.useState(false);
	const [recommendationLoading, setRecommendationLoading] =
		React.useState(false);
	const [recommendationError, setRecommendationError] = React.useState<
		string | null
	>(null);
	const [recommendationResponse, setRecommendationResponse] =
		React.useState<RecommendationGenerateResponse | null>(null);
	const [clickedPapers, setClickedPapers] = React.useState<Set<string>>(
		new Set(),
	);

	const handleGenerateRecommendations = async () => {
		setRecommendationLoading(true);
		setRecommendationError(null);
		setClickedPapers(new Set());
		try {
			const res = await generateRecommendations(sessionId, token, userQuery);
			setRecommendationResponse(res);
			setRecommendationOpen(true);
		} catch (err) {
			log.error("handle_generate", "Failed to fetch recommendations", {
				error: err,
			});
			setRecommendationError(
				t(
					"error.load_recommendations_failed",
					"Failed to generate recommendations. Please try again.",
				),
			);
		} finally {
			setRecommendationLoading(false);
		}
	};

	const handlePaperClick = (paperTitle: string, url: string | undefined) => {
		setClickedPapers((prev) => new Set(prev).add(paperTitle));
		const target =
			url ||
			`https://scholar.google.com/scholar?q=${encodeURIComponent(paperTitle)}`;
		window.open(target, "_blank", "noopener,noreferrer");
	};

	if (!recommendationOpen && !recommendationLoading) {
		return (
			<div className="space-y-4">
				<div className="flex flex-col items-center justify-center py-8 text-center">
					<div className="w-16 h-16 bg-orange-100 text-orange-500 rounded-full flex items-center justify-center mb-4">
						<svg
							className="w-8 h-8"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
							/>
						</svg>
					</div>
					<h3 className="text-lg font-bold text-slate-800 mb-2">
						{t("recommendation.explore_title", "Explore Next Papers")}
					</h3>
					<p className="text-sm text-slate-500 mb-5">
						{t(
							"recommendation.explore_description",
							"Based on your reading history and behavior, we'll generate personalized recommendations.",
						)}
					</p>
					<div className="w-full mb-5">
						<textarea
							value={userQuery}
							onChange={(e) => setUserQuery(e.target.value)}
							placeholder={t(
								"recommendation.user_query_placeholder",
								"どのような論文が読みたいですか？（例: 強化学習の最新動向、医療画像認識）",
							)}
							rows={3}
							className="w-full px-3 py-2 text-sm text-slate-700 bg-white border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent placeholder:text-slate-400 transition-shadow"
						/>
					</div>
					<button
						type="button"
						onClick={handleGenerateRecommendations}
						className="px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white font-bold rounded-xl shadow-lg shadow-orange-600/30 transition-transform active:scale-95 flex items-center gap-2"
					>
						<svg
							className="w-5 h-5 animate-pulse"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M13 10V3L4 14h7v7l9-11h-7z"
							/>
						</svg>
						{t("summary.generate_recommend", "Generate Recommendations")}
					</button>
					{recommendationError && (
						<p className="mt-4 text-xs text-red-500">{recommendationError}</p>
					)}
				</div>
			</div>
		);
	}

	if (recommendationLoading) {
		return (
			<div className="h-full flex flex-col items-center justify-center gap-4 py-12">
				<div className="flex space-x-2">
					<div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
					<div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
					<div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce" />
				</div>
				<p className="text-sm font-medium text-slate-500 animate-pulse">
					{t(
						"recommendation.analyzing",
						"Analyzing user profile and generating insights...",
					)}
				</p>
			</div>
		);
	}

	if (recommendationResponse) {
		return (
			<div className="space-y-4">
				<div className="space-y-3">
					<h4 className="text-sm font-bold text-slate-700">
						{t("recommendation.top_recommendations", "Top Recommendations")}
					</h4>
					{recommendationResponse.recommendations.map((paper, idx) => (
						<div
							key={idx}
							className="bg-white border border-slate-100 rounded-xl p-4 shadow-sm"
						>
							<div className="flex justify-end mb-2">
								<CopyButton text={paper.title} />
							</div>
							<h5 className="font-bold text-slate-800 text-sm mb-1 leading-tight">
								{paper.title}
							</h5>
							{paper.authors && (
								<p className="text-xs text-slate-400 mb-2 font-medium truncate">
									{paper.authors.map((a) => a.name).join(", ")}{" "}
									{paper.year ? `(${paper.year})` : ""}
								</p>
							)}
							<MarkdownContent className="prose prose-sm max-w-none text-sm text-slate-600 leading-relaxed mb-3">
								{paper.abstract}
							</MarkdownContent>
							<div className="flex items-center justify-between">
								<button
									type="button"
									onClick={() =>
										handlePaperClick(
											paper.title,
											paper.openAccessPdf?.url || paper.url,
										)
									}
									className={`text-xs font-bold px-3 py-2 rounded-lg border flex items-center gap-1.5 transition-colors ${clickedPapers.has(paper.title) ? "bg-green-50 text-green-700 border-green-200" : "bg-orange-50 hover:bg-orange-100 text-orange-700 border-orange-100"}`}
								>
									<svg
										className="w-3.5 h-3.5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											strokeLinecap="round"
											strokeLinejoin="round"
											strokeWidth="2.5"
											d="M12 6v6m0 0v6m0-6h6m-6 0H6"
										/>
									</svg>
									{clickedPapers.has(paper.title)
										? t("recommendation.status_clicked", "Clicked")
										: t("recommendation.action_explore", "Explore")}
								</button>
								{paper.citationCount !== undefined && (
									<span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-2 py-1 rounded">
										Citations: {paper.citationCount}
									</span>
								)}
							</div>
							<FeedbackSection
								compact
								sessionId={sessionId}
								targetType="recommendation"
								targetId={paper.title}
								traceId={recommendationResponse.trace_id}
							/>
						</div>
					))}
				</div>

				<div className="pb-8 flex justify-center">
					<button
						type="button"
						onClick={() => {
							setRecommendationOpen(false);
							setRecommendationResponse(null);
						}}
						className="text-xs text-slate-400 hover:text-slate-600 font-medium underline"
					>
						Start Over
					</button>
				</div>
			</div>
		);
	}

	return null;
};

export default DiscoverPanel;

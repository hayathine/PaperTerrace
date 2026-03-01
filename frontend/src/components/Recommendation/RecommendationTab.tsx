import type React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/contexts/AuthContext";
import {
	generateRecommendations,
	type RecommendationGenerateResponse,
} from "@/lib/recommendation";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";

interface RecommendationTabProps {
	sessionId: string;
}

const RecommendationTab: React.FC<RecommendationTabProps> = ({ sessionId }) => {
	const { t } = useTranslation();
	const { token } = useAuth();
	const [isOpen, setIsOpen] = useState(false);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [response, setResponse] =
		useState<RecommendationGenerateResponse | null>(null);
	const [clickedPapers, setClickedPapers] = useState<Set<string>>(new Set());

	const handleGenerate = async () => {
		setIsLoading(true);
		setError(null);
		setClickedPapers(new Set());
		try {
			const res = await generateRecommendations(sessionId, token);
			setResponse(res);
			setIsOpen(true);
		} catch (err) {
			console.error("Failed to fetch recommendations:", err);
			setError(
				t(
					"error.load_recommendations_failed",
					"Failed to generate recommendations. Please try again.",
				),
			);
		} finally {
			setIsLoading(false);
		}
	};

	const handlePaperClick = (paperTitle: string, url: string | undefined) => {
		setClickedPapers((prev) => new Set(prev).add(paperTitle));

		const target =
			url ||
			`https://scholar.google.com/scholar?q=${encodeURIComponent(paperTitle)}`;
		window.open(target, "_blank", "noopener,noreferrer");
	};

	return (
		<div className="flex flex-col h-full bg-slate-50 overflow-hidden">
			{!isOpen && !isLoading ? (
				<div className="flex flex-col items-center justify-center p-6 h-full text-center">
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
					<p className="text-sm text-slate-500 mb-6">
						{t(
							"recommendation.explore_description",
							"Based on your reading history and behavior, we'll generate personalized recommendations.",
						)}
					</p>
					<button
						type="button"
						onClick={handleGenerate}
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
					{error && <p className="mt-4 text-xs text-red-500">{error}</p>}
				</div>
			) : (
				<div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
					{isLoading ? (
						<div className="h-full flex flex-col items-center justify-center gap-4">
							<div className="flex space-x-2">
								<div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
								<div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
								<div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce"></div>
							</div>
							<p className="text-sm font-medium text-slate-500 animate-pulse">
								{t(
									"recommendation.analyzing",
									"Analyzing user profile and generating insights...",
								)}
							</p>
						</div>
					) : response ? (
						<div className="space-y-6">
							<div className="bg-orange-50 border border-orange-100 rounded-xl p-4">
								<h4 className="text-sm font-bold text-orange-900 mb-2">
									{t(
										"recommendation.reasoning_title",
										"Recommendation Reasoning",
									)}
								</h4>
								<MarkdownContent className="prose prose-xs max-w-none text-xs text-orange-700 leading-relaxed mb-3">
									{response.reasoning}
								</MarkdownContent>
								<div className="flex flex-wrap gap-2">
									<span className="px-2 py-1 bg-white shadow-sm border border-orange-100 rounded-md text-xs font-bold text-orange-600 uppercase tracking-wider">
										Skill Level: {response.knowledge_level}
									</span>
									{response.search_queries.slice(0, 2).map((q, idx) => (
										<span
											key={idx}
											className="px-2 py-1 bg-white shadow-sm border border-orange-100 rounded-md text-xs font-bold text-slate-500"
										>
											🔍 {q}
										</span>
									))}
								</div>
							</div>

							<div className="space-y-3">
								<h4 className="text-sm font-bold border-b border-slate-200 pb-2 text-slate-700">
									{t(
										"recommendation.top_recommendations",
										"Top Recommendations",
									)}
								</h4>
								{response.recommendations.map((paper, idx) => (
									<div
										key={idx}
										className="bg-white border border-slate-200 rounded-xl p-3 sm:p-4 shadow-sm hover:shadow-md transition-shadow"
									>
										<h5 className="font-bold text-slate-800 text-sm mb-1 leading-tight">
											{paper.title}
										</h5>
										{paper.authors && (
											<p className="text-xs text-slate-400 mb-2 font-medium truncate">
												{paper.authors.map((a) => a.name).join(", ")}{" "}
												{paper.year ? `(${paper.year})` : ""}
											</p>
										)}
										<p className="text-xs text-slate-600 line-clamp-3 mb-3">
											{paper.abstract}
										</p>
										<div className="flex items-center justify-between">
											<button
												type="button"
												onClick={() =>
													handlePaperClick(
														paper.title,
														paper.openAccessPdf?.url || paper.url,
													)
												}
												className={`text-xs font-bold px-3 py-2 sm:py-1.5 rounded-lg border flex items-center gap-1.5 transition-colors ${clickedPapers.has(paper.title) ? "bg-green-50 text-green-700 border-green-200" : "bg-orange-50 hover:bg-orange-100 text-orange-700 border-orange-100"}`}
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
									</div>
								))}
							</div>

							{/* Feedback UI */}
							<FeedbackSection
								sessionId={sessionId}
								targetType="recommendation"
								targetId={Array.from(clickedPapers)[0]}
							/>
							<div className="pb-8 flex justify-center">
								<button
									type="button"
									onClick={() => {
										setIsOpen(false);
										setResponse(null);
									}}
									className="text-xs text-slate-400 hover:text-slate-600 font-medium underline"
								>
									Start Over
								</button>
							</div>
						</div>
					) : null}
				</div>
			)}
		</div>
	);
};

export default RecommendationTab;

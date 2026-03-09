import React, { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import {
	generateRecommendations,
	type RecommendationGenerateResponse,
} from "@/lib/recommendation";
import { useAuth } from "../../contexts/AuthContext";
import { useLoading } from "../../contexts/LoadingContext";
import { usePaperCache } from "../../db/hooks";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";
import type { CritiqueResponse } from "./types";

const log = createLogger("Summary");

interface SummaryProps {
	sessionId: string;
	paperId?: string | null;
	isAnalyzing?: boolean;
	isActive?: boolean;
}

type Mode = "summary" | "critique" | "discover";

const Summary: React.FC<SummaryProps> = ({
	sessionId,
	paperId,
	isAnalyzing = false,
	isActive = false,
}) => {
	const { t, i18n } = useTranslation();
	const { token } = useAuth();
	const { startLoading, stopLoading } = useLoading();
	const { getCachedPaper, savePaperToCache } = usePaperCache();

	const [mode, setMode] = useState<Mode>("summary");
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [summaryData, setSummaryData] = useState<string | null>(null);
	const [summaryTraceId, setSummaryTraceId] = useState<string | undefined>(
		undefined,
	);
	const [critiqueData, setCritiqueData] = useState<CritiqueResponse | null>(
		null,
	);
	const [critiqueTraceId, setCritiqueTraceId] = useState<string | undefined>(
		undefined,
	);

	// Recommendation state
	const [recommendationOpen, setRecommendationOpen] = useState(false);
	const [recommendationLoading, setRecommendationLoading] = useState(false);
	const [recommendationError, setRecommendationError] = useState<string | null>(
		null,
	);
	const [recommendationResponse, setRecommendationResponse] =
		useState<RecommendationGenerateResponse | null>(null);
	const [clickedPapers, setClickedPapers] = useState<Set<string>>(new Set());

	// Reset data when paperId changes
	React.useEffect(() => {
		setSummaryData(null);
		setCritiqueData(null);
		setError(null);
	}, [paperId]);

	// Load summary from cache on mount or when paperId changes
	React.useEffect(() => {
		if (paperId && !summaryData) {
			getCachedPaper(paperId).then((cached) => {
				if (cached?.full_summary) {
					log.info("load_cache", "Loading summary from IndexedDB cache");

					setSummaryData(cached.full_summary);
				}
			});
		}
	}, [paperId, getCachedPaper, summaryData]);

	const handleSummarize = useCallback(
		async (force = false) => {
			setLoading(true);
			startLoading(t("summary.processing"));
			setError(null);
			try {
				const formData = new FormData();
				formData.append("session_id", sessionId);
				formData.append("lang", i18n.language);
				if (paperId) formData.append("paper_id", paperId);
				if (force) formData.append("force", "true");

				const headers: HeadersInit = {};
				if (token) headers.Authorization = `Bearer ${token}`;

				const res = await fetch(`${API_URL}/api/summarize`, {
					method: "POST",
					headers,
					body: formData,
				});
				if (!res.ok) {
					const errorText = await res.text();
					throw new Error(errorText || `Status ${res.status}`);
				}
				const data = await res.json();
				if (data.summary) {
					setSummaryData(data.summary);
					setSummaryTraceId(data.trace_id);
					// Save to IndexedDB
					if (paperId) {
						getCachedPaper(paperId).then((cached) => {
							savePaperToCache({
								...(cached || {
									id: paperId,
									file_hash: "",
									title: "Untitled",
									last_accessed: Date.now(),
								}),
								full_summary: data.summary,
								last_accessed: Date.now(),
							});
						});
					}
				} else if (data.abstract) {
					setSummaryData(data.abstract);
				} else {
					log.error("handle_summarize", "Summary not found in response", {
						data,
					});
					setError(t("common.errors.processing"));
				}
			} catch (e: any) {
				log.error("handle_summarize", "Summary generation failed", {
					error: e,
				});
				setError(t("common.errors.processing"));
			} finally {
				setLoading(false);
				stopLoading();
			}
		},
		[
			sessionId,
			paperId,
			i18n.language,
			t,
			startLoading,
			stopLoading,
			getCachedPaper,
			savePaperToCache,
		],
	);

	const handleCritique = useCallback(async () => {
		setLoading(true);
		startLoading(t("summary.processing"));
		setError(null);
		try {
			const formData = new FormData();
			formData.append("session_id", sessionId);
			formData.append("lang", i18n.language);
			const headers: HeadersInit = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			const res = await fetch(`${API_URL}/api/critique`, {
				method: "POST",
				headers,
				body: formData,
			});

			if (!res.ok) {
				const errorText = await res.text();
				throw new Error(errorText || `Status ${res.status}`);
			}
			const data = await res.json();
			setCritiqueData(data);
			setCritiqueTraceId(data.trace_id);
		} catch (e: any) {
			log.error("handle_critique", "Critique generation failed", { error: e });
			setError(t("common.errors.processing"));
		} finally {
			setLoading(false);
			stopLoading();
		}
	}, [sessionId, i18n.language, t, startLoading, stopLoading]);

	// Auto-fetch summary when analysis completes (not during analysis)
	const prevAnalyzingRef = React.useRef(isAnalyzing);
	React.useEffect(() => {
		const wasAnalyzing = prevAnalyzingRef.current;
		prevAnalyzingRef.current = isAnalyzing;

		// Don't fetch while still analyzing
		if (isAnalyzing) return;

		// When analysis just completed (all page images are ready), fetch immediately
		// regardless of whether the Summary tab is currently active.
		if (sessionId && paperId && wasAnalyzing) {
			handleSummarize(false);
			return;
		}

		// Lazy-fetch when the Summary tab becomes active but no data is available yet.
		if (isActive && sessionId && paperId && !summaryData) {
			handleSummarize(false);
		}
	}, [sessionId, paperId, isAnalyzing, summaryData, handleSummarize, isActive]);

	const handleGenerateRecommendations = async () => {
		setRecommendationLoading(true);
		setRecommendationError(null);
		setClickedPapers(new Set());
		try {
			const res = await generateRecommendations(sessionId, token);
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

	return (
		<div className="flex flex-col h-full bg-slate-50">
			<div className="flex p-2 bg-white border-b border-slate-100 gap-2 overflow-x-auto">
				<button
					type="button"
					onClick={() => setMode("summary")}
					className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all whitespace-nowrap ${mode === "summary" ? "bg-orange-50 text-orange-600" : "text-slate-400"}`}
				>
					{t("summary.modes.summary")}
				</button>
				<button
					type="button"
					onClick={() => setMode("critique")}
					className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all whitespace-nowrap ${mode === "critique" ? "bg-red-50 text-red-600" : "text-slate-400"}`}
				>
					{t("summary.modes.critique")}
				</button>
				<button
					type="button"
					onClick={() => setMode("discover")}
					className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all whitespace-nowrap ${mode === "discover" ? "bg-orange-50 text-orange-600" : "text-slate-400"}`}
				>
					{t("sidebar.tabs.discover")}
				</button>
			</div>

			<div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
				{error && (
					<div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-600">
						{error}
					</div>
				)}

				{loading && (mode !== "summary" || summaryData) && (
					<div className="text-center py-10 text-slate-400 text-xs animate-pulse">
						{t("summary.processing")}
					</div>
				)}

				{mode === "summary" && (
					<div className="space-y-4">
						{!summaryData && (
							<div className="text-center py-8">
								{isAnalyzing || loading || (!error && paperId) ? (
									<div className="flex flex-col items-center gap-3">
										<div className="w-8 h-8 border-2 border-orange-100 border-t-orange-600 rounded-full animate-spin" />
										<p className="text-sm font-bold text-orange-600 animate-pulse tracking-widest">
											{t("summary.generating", "生成中...")}
										</p>
										<p className="text-xs text-slate-400 font-medium">
											{t(
												"summary.generating_hint",
												"解析完了後に自動で要約を生成します",
											)}
										</p>
									</div>
								) : (
									<>
										<p className="text-xs text-slate-400 mb-4 font-medium">
											{error
												? "要約の生成に失敗しました。再試行してください。"
												: t("summary.hints.summary")}
										</p>
										<button
											type="button"
											onClick={() => handleSummarize(false)}
											className="px-5 py-2.5 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-bold shadow-md shadow-orange-200 transition-all active:scale-95"
										>
											{t("summary.generate")}
										</button>
									</>
								)}
							</div>
						)}
						{summaryData && !loading && (
							<div>
								<div className="flex justify-end mb-2 gap-1">
									<CopyButton text={summaryData} />
									<button
										type="button"
										onClick={() => handleSummarize(true)}
										className="px-3 py-1 text-xs text-slate-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-all flex items-center gap-1"
										title={t("summary.regenerate", "再生成")}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											width="12"
											height="12"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											strokeWidth="2"
											strokeLinecap="round"
											strokeLinejoin="round"
										>
											<path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
										</svg>
										{t("summary.regenerate", "再生成")}
									</button>
								</div>
								<MarkdownContent className="prose prose-sm max-w-none text-sm text-slate-600 leading-relaxed bg-white p-4 rounded-xl border border-slate-100 shadow-sm">
									{summaryData || ""}
								</MarkdownContent>
								<FeedbackSection
									sessionId={sessionId}
									targetType="summary"
									targetId={paperId || undefined}
									traceId={summaryTraceId}
								/>
							</div>
						)}
					</div>
				)}

				{mode === "discover" && (
					<div className="space-y-4">
						{!recommendationOpen && !recommendationLoading ? (
							<div className="flex flex-col items-center justify-center py-12 text-center">
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
									<p className="mt-4 text-xs text-red-500">
										{recommendationError}
									</p>
								)}
							</div>
						) : recommendationLoading ? (
							<div className="h-full flex flex-col items-center justify-center gap-4 py-12">
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
						) : recommendationResponse ? (
							<div className="space-y-4">
								<div className="space-y-3">
									<h4 className="text-sm font-bold text-slate-700">
										{t(
											"recommendation.top_recommendations",
											"Top Recommendations",
										)}
									</h4>
									{recommendationResponse.recommendations.map((paper, idx) => (
										<div
											key={idx}
											className="bg-white border border-slate-100 rounded-xl p-4 shadow-sm"
										>
											<div className="flex justify-end mb-2">
												<CopyButton
													text={`${paper.title}\n${paper.abstract}`}
												/>
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
						) : null}
					</div>
				)}

				{!loading && mode === "critique" && (
					<div className="space-y-4">
						{!critiqueData && (
							<div className="text-center py-8">
								<p className="text-xs text-slate-400 mb-4">
									{t("summary.hints.critique")}
								</p>
								<button
									type="button"
									onClick={handleCritique}
									className="px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-bold shadow-sm hover:bg-red-700"
								>
									{t("summary.start_critique")}
								</button>
							</div>
						)}
						{critiqueData && (
							<div className="space-y-4">
								<div className="bg-white p-4 rounded-xl border border-red-100 shadow-sm space-y-4 relative">
									<div className="absolute top-2 right-2">
										<CopyButton
											text={[
												critiqueData.overall_assessment,
												...(critiqueData.hidden_assumptions?.map(
													(h) => `${h.assumption}: ${h.risk}`,
												) || []),
												...(critiqueData.unverified_conditions?.map(
													(h) => `${h.condition}: ${h.impact}`,
												) || []),
												...(critiqueData.reproducibility_risks?.map(
													(h) => `${h.risk}: ${h.detail}`,
												) || []),
											].join("\n\n")}
										/>
									</div>
									<MarkdownContent className="prose prose-sm max-w-none text-sm text-slate-700 leading-relaxed font-medium mb-4">
										{critiqueData.overall_assessment || ""}
									</MarkdownContent>

									{critiqueData.hidden_assumptions &&
										critiqueData.hidden_assumptions.length > 0 && (
											<div className="bg-red-50 p-4 rounded-lg flex flex-col gap-2">
												<h4 className="text-xs font-bold text-red-800 uppercase mb-2">
													{t("summary.assumptions")}
												</h4>

												<div className="space-y-4">
													{critiqueData.hidden_assumptions.map((h, i) => (
														<div key={i} className="text-sm text-red-700">
															<span className="font-bold">
																● {h.assumption}
															</span>
															<MarkdownContent className="prose prose-xs max-w-none ml-4 mt-1 opacity-80 text-xs">
																{h.risk}
															</MarkdownContent>
														</div>
													))}
												</div>
											</div>
										)}

									{critiqueData.unverified_conditions &&
										critiqueData.unverified_conditions.length > 0 && (
											<div className="bg-orange-50 p-4 rounded-lg flex flex-col gap-2">
												<h4 className="text-xs font-bold text-orange-800 uppercase mb-2">
													{t("summary.unverified")}
												</h4>

												<div className="space-y-4">
													{critiqueData.unverified_conditions.map((h, i) => (
														<div key={i} className="text-sm text-orange-700">
															<span className="font-bold">● {h.condition}</span>
															<MarkdownContent className="prose prose-xs max-w-none ml-4 mt-1 opacity-80 text-xs">
																{h.impact}
															</MarkdownContent>
														</div>
													))}
												</div>
											</div>
										)}

									{critiqueData.reproducibility_risks &&
										critiqueData.reproducibility_risks.length > 0 && (
											<div className="bg-slate-50 p-4 rounded-lg border border-slate-200 flex flex-col gap-2">
												<h4 className="text-xs font-bold text-slate-800 uppercase mb-2">
													{t("summary.reproducibility")}
												</h4>

												<div className="space-y-4">
													{critiqueData.reproducibility_risks.map((h, i) => (
														<div key={i} className="text-sm text-slate-700">
															<span className="font-bold">● {h.risk}</span>
															<MarkdownContent className="prose prose-xs max-w-none ml-4 mt-1 opacity-80 text-xs">
																{h.detail}
															</MarkdownContent>
														</div>
													))}
												</div>
											</div>
										)}
								</div>
								<FeedbackSection
									sessionId={sessionId}
									targetType="critique"
									targetId={paperId || undefined}
									traceId={critiqueTraceId}
								/>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

export default Summary;

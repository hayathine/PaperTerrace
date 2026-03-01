import React, { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { useLoading } from "../../contexts/LoadingContext";
import { usePaperCache } from "../../db/hooks";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";
import type { CritiqueResponse } from "./types";

interface SummaryProps {
	sessionId: string;
	paperId?: string | null;
	isAnalyzing?: boolean;
}

type Mode = "summary" | "critique";

const Summary: React.FC<SummaryProps> = ({
	sessionId,
	paperId,
	isAnalyzing = false,
}) => {
	const { t, i18n } = useTranslation();
	const { startLoading, stopLoading } = useLoading();
	const { getCachedPaper, savePaperToCache } = usePaperCache();

	const [mode, setMode] = useState<Mode>("summary");
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [summaryData, setSummaryData] = useState<string | null>(null);
	const [critiqueData, setCritiqueData] = useState<CritiqueResponse | null>(
		null,
	);

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
					console.log("[Summary] Loading from IndexedDB cache");
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

				const res = await fetch(`${API_URL}/api/summarize`, {
					method: "POST",
					body: formData,
				});
				if (!res.ok) {
					const errorText = await res.text();
					throw new Error(errorText || `Status ${res.status}`);
				}
				const data = await res.json();
				if (data.summary) {
					setSummaryData(data.summary);
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
					setError(data.error || "Summary not found in response");
				}
			} catch (e: any) {
				setError(`Error: ${e.message}`);
				console.error(e);
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
			const res = await fetch(`${API_URL}/api/critique`, {
				method: "POST",
				body: formData,
			});

			if (!res.ok) {
				const errorText = await res.text();
				throw new Error(errorText || `Status ${res.status}`);
			}
			const data = await res.json();
			setCritiqueData(data);
		} catch (e: any) {
			setError(`Error: ${e.message}`);
			console.error(e);
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

		// Fetch when: analysis just finished, or initial load (not analyzing)
		// Only fetch if not already in state. (Initial load will be handled by the direct useEffect above if cached)
		if (sessionId && paperId && (wasAnalyzing || !summaryData)) {
			// If we just finished analyzing, or we have no data and it's not and we are not analyzing
			handleSummarize(false);
		}
	}, [sessionId, paperId, isAnalyzing, summaryData, handleSummarize]);

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
								/>
							</div>
						)}
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

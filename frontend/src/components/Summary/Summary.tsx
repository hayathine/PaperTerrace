import React, { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { useLoading } from "../../contexts/LoadingContext";
import type { CritiqueResponse, RecommendResponse } from "./types";

interface SummaryProps {
	sessionId: string;
	paperId?: string | null;
	isAnalyzing?: boolean;
}

type Mode = "summary" | "critique" | "recommend";

const Summary: React.FC<SummaryProps> = ({
	sessionId,
	paperId,
	isAnalyzing = false,
}) => {
	const { t, i18n } = useTranslation();
	const { startLoading, stopLoading } = useLoading();
	const [mode, setMode] = useState<Mode>("summary");

	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [summaryData, setSummaryData] = useState<string | null>(null);
	const [critiqueData, setCritiqueData] = useState<CritiqueResponse | null>(
		null,
	);
	const [recommendData, setRecommendData] = useState<RecommendResponse | null>(
		null,
	);

	// Reset data when paperId changes
	React.useEffect(() => {
		setSummaryData(null);
		setCritiqueData(null);
		setRecommendData(null);
		setError(null);
	}, [paperId]);

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
		[sessionId, paperId, i18n.language, t, startLoading, stopLoading],
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

	const handleRecommend = useCallback(async () => {
		setLoading(true);
		startLoading(t("summary.processing"));
		setError(null);
		try {
			const formData = new FormData();
			formData.append("session_id", sessionId);
			formData.append("lang", i18n.language);
			const res = await fetch(`${API_URL}/api/recommend`, {
				method: "POST",
				body: formData,
			});

			if (!res.ok) {
				const errorText = await res.text();
				throw new Error(errorText || `Status ${res.status}`);
			}
			const data = await res.json();
			setRecommendData(data);
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
		if (sessionId && paperId && (wasAnalyzing || !summaryData)) {
			handleSummarize(false);
		}
	}, [sessionId, paperId, isAnalyzing]);

	return (
		<div className="flex flex-col h-full bg-slate-50">
			<div className="flex p-2 bg-white border-b border-slate-100 gap-2 overflow-x-auto">
				<button
					type="button"
					onClick={() => setMode("summary")}
					className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all whitespace-nowrap ${mode === "summary" ? "bg-indigo-50 text-indigo-600" : "text-slate-400"}`}
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
					onClick={() => setMode("recommend")}
					className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-all whitespace-nowrap ${mode === "recommend" ? "bg-emerald-50 text-emerald-600" : "text-slate-400"}`}
				>
					{t("summary.modes.recommend")}
				</button>
			</div>

			<div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
				{error && (
					<div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-600">
						{error}
					</div>
				)}

				{loading && (
					<div className="text-center py-10 text-slate-400 text-xs animate-pulse">
						{t("summary.processing")}
					</div>
				)}

				{!loading && mode === "summary" && (
					<div className="space-y-4">
						{!summaryData && (
							<div className="text-center py-8">
								{isAnalyzing ? (
									<div className="flex flex-col items-center gap-3">
										<div className="w-8 h-8 border-2 border-slate-200 border-t-indigo-500 rounded-full animate-spin" />
										<p className="text-xs text-slate-400 animate-pulse">
											{t("summary.analyzing", "論文を解析中です...")}
										</p>
										<p className="text-[10px] text-slate-300">
											{t(
												"summary.analyzing_hint",
												"解析完了後に自動で要約を生成します",
											)}
										</p>
									</div>
								) : (
									<>
										<p className="text-xs text-slate-400 mb-4">
											{t("summary.hints.summary")}
										</p>
										<button
											type="button"
											onClick={() => handleSummarize(false)}
											className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold shadow-sm hover:bg-indigo-700"
										>
											{t("summary.generate")}
										</button>
									</>
								)}
							</div>
						)}
						{summaryData && (
							<div>
								<div className="flex justify-end mb-2">
									<button
										type="button"
										onClick={() => handleSummarize(true)}
										className="px-3 py-1 text-xs text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all flex items-center gap-1"
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
								<div className="prose prose-sm max-w-none text-sm text-slate-600 leading-relaxed whitespace-pre-wrap bg-white p-4 rounded-xl border border-slate-100 shadow-sm">
									{summaryData}
								</div>
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
							<div className="bg-white p-4 rounded-xl border border-red-100 shadow-sm space-y-4">
								<div className="text-sm text-slate-700 leading-relaxed font-medium mb-4">
									{critiqueData.overall_assessment}
								</div>

								{critiqueData.hidden_assumptions &&
									critiqueData.hidden_assumptions.length > 0 && (
										<div className="bg-red-50 p-4 rounded-lg flex flex-col gap-2">
											<h4 className="text-xs font-bold text-red-800 uppercase mb-2">
												{t("summary.assumptions")}
											</h4>

											<div className="space-y-4">
												{critiqueData.hidden_assumptions.map((h, i) => (
													<div key={i} className="text-sm text-red-700">
														<span className="font-bold">● {h.assumption}</span>
														<p className="ml-4 mt-1 opacity-80 text-xs">
															{h.risk}
														</p>
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
														<p className="ml-4 mt-1 opacity-80 text-xs">
															{h.impact}
														</p>
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
														<p className="ml-4 mt-1 opacity-80 text-xs">
															{h.detail}
														</p>
													</div>
												))}
											</div>
										</div>
									)}
							</div>
						)}
					</div>
				)}

				{!loading && mode === "recommend" && (
					<div className="space-y-4">
						{!recommendData && (
							<div className="text-center py-8">
								<p className="text-xs text-slate-400 mb-4">
									{t("summary.hints.recommend")}
								</p>
								<button
									type="button"
									onClick={handleRecommend}
									className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold shadow-sm hover:bg-emerald-700"
								>
									{t("summary.generate_recommend")}
								</button>
							</div>
						)}
						{recommendData && (
							<div className="space-y-4">
								{recommendData.search_queries && (
									<div className="flex flex-wrap gap-2">
										{recommendData.search_queries.map(
											(q: string, i: number) => (
												<span
													key={i}
													className="bg-emerald-50 text-emerald-700 text-xs px-2.5 py-1 rounded-full border border-emerald-100 italic"
												>
													"{q}"
												</span>
											),
										)}
									</div>
								)}
								{recommendData.related_papers &&
									recommendData.related_papers.length > 0 && (
										<div className="space-y-3">
											{recommendData.related_papers.map((p: any, i: number) => (
												<div
													key={i}
													className="bg-white p-4 rounded-lg border border-emerald-100 shadow-sm hover:shadow-md transition-shadow"
												>
													<p className="text-sm font-bold text-slate-700">
														{p.title}
													</p>
													<div className="flex items-center gap-2 mt-1.5">
														<span className="text-xs font-medium text-slate-400">
															{p.year || "n/a"}
														</span>
														{p.url && (
															<a
																href={p.url}
																target="_blank"
																rel="noopener noreferrer"
																className="text-xs text-indigo-500 hover:text-indigo-600 hover:underline font-medium"
															>
																View Paper
															</a>
														)}
													</div>
													{p.abstract && (
														<p className="text-xs text-slate-500 mt-2.5 line-clamp-3 italic leading-relaxed">
															{p.abstract}
														</p>
													)}
												</div>
											))}
										</div>
									)}
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

export default Summary;

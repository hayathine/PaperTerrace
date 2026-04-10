import React, { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";
import { createLogger } from "@/lib/logger";
import { useAuth } from "../../contexts/AuthContext";
import { useLoading } from "../../contexts/LoadingContext";
import { usePaperCache } from "../../db/hooks";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";

const log = createLogger("SummaryPanel");

interface SummaryPanelProps {
	sessionId: string;
	paperId?: string | null;
	isAnalyzing?: boolean;
	isActive?: boolean;
}

const SummaryPanel: React.FC<SummaryPanelProps> = ({
	sessionId,
	paperId,
	isAnalyzing = false,
	isActive = false,
}) => {
	const { t, i18n } = useTranslation();
	const { token } = useAuth();
	const { startLoading, stopLoading } = useLoading();
	const { getCachedPaper, savePaperToCache } = usePaperCache();

	const [loading, setLoading] = React.useState(false);
	const [error, setError] = React.useState<string | null>(null);
	const [summaryData, setSummaryData] = React.useState<string | null>(null);
	const [summaryTraceId, setSummaryTraceId] = React.useState<
		string | undefined
	>(undefined);

	// Reset on paperId change
	React.useEffect(() => {
		setSummaryData(null);
		setError(null);
	}, [paperId]);

	// Load from IndexedDB cache
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
				const lang = i18n.language.startsWith("ja") ? "ja" : "en";
				formData.append("lang", lang);
				if (paperId) formData.append("paper_id", paperId);
				if (force) formData.append("force", "true");

				const res = await fetch(`${API_URL}/api/summarize`, {
					method: "POST",
					headers: buildAuthHeaders(token),
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
			} catch (e: unknown) {
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
			token,
		],
	);

	// Auto-fetch after analysis completes or when tab becomes active
	const prevAnalyzingRef = React.useRef(isAnalyzing);
	React.useEffect(() => {
		const wasAnalyzing = prevAnalyzingRef.current;
		prevAnalyzingRef.current = isAnalyzing;

		if (isAnalyzing) return;

		if (sessionId && paperId && wasAnalyzing) {
			handleSummarize(false);
			return;
		}

		if (isActive && sessionId && paperId && !summaryData) {
			handleSummarize(false);
		}
	}, [sessionId, paperId, isAnalyzing, summaryData, handleSummarize, isActive]);

	return (
		<div className="space-y-4">
			{error && (
				<div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-600">
					{error}
				</div>
			)}
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
						<CopyButton text={summaryData} traceId={summaryTraceId} />
						<button
							type="button"
							onClick={() => {
								const blob = new Blob([summaryData], {
									type: "text/markdown;charset=utf-8",
								});
								const url = URL.createObjectURL(blob);
								const a = document.createElement("a");
								a.href = url;
								a.download = `summary_${paperId ?? "paper"}.md`;
								a.click();
								URL.revokeObjectURL(url);
							}}
							className="px-3 py-1 text-xs text-slate-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-all flex items-center gap-1"
							title="Markdownでダウンロード"
						>
							<svg
								className="w-3 h-3"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
								/>
							</svg>
							MD
						</button>
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
	);
};

export default SummaryPanel;

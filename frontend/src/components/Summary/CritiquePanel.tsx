import React, { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";
import { createLogger } from "@/lib/logger";
import { useAuth } from "../../contexts/AuthContext";
import { useLoading } from "../../contexts/LoadingContext";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";
import type { CritiqueResponse } from "./types";

const log = createLogger("CritiquePanel");

interface CritiquePanelProps {
	sessionId: string;
	paperId?: string | null;
}

const CritiquePanel: React.FC<CritiquePanelProps> = ({
	sessionId,
	paperId,
}) => {
	const { t, i18n } = useTranslation();
	const { token } = useAuth();
	const { startLoading, stopLoading } = useLoading();

	const [loading, setLoading] = React.useState(false);
	const [error, setError] = React.useState<string | null>(null);
	const [critiqueData, setCritiqueData] =
		React.useState<CritiqueResponse | null>(null);
	const [critiqueTraceId, setCritiqueTraceId] = React.useState<
		string | undefined
	>(undefined);

	// Reset on paperId change
	React.useEffect(() => {
		setCritiqueData(null);
		setError(null);
	}, [paperId]);

	const handleCritique = useCallback(async () => {
		setLoading(true);
		startLoading(t("summary.processing"));
		setError(null);
		try {
			const formData = new FormData();
			formData.append("session_id", sessionId);
			formData.append("lang", i18n.language.startsWith("ja") ? "ja" : "en");

			const res = await fetch(`${API_URL}/api/critique`, {
				method: "POST",
				headers: buildAuthHeaders(token),
				body: formData,
			});
			if (!res.ok) {
				const errorText = await res.text();
				throw new Error(errorText || `Status ${res.status}`);
			}
			const data = await res.json();
			setCritiqueData(data);
			setCritiqueTraceId(data.trace_id);
		} catch (e: unknown) {
			log.error("handle_critique", "Critique generation failed", { error: e });
			setError(t("common.errors.processing"));
		} finally {
			setLoading(false);
			stopLoading();
		}
	}, [sessionId, i18n.language, t, startLoading, stopLoading, token]);

	if (loading) {
		return (
			<div className="text-center py-10 text-slate-400 text-xs animate-pulse">
				{t("summary.processing")}
			</div>
		);
	}

	return (
		<div className="space-y-4">
			{error && (
				<div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-600">
					{error}
				</div>
			)}
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
								traceId={critiqueTraceId}
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
												<span className="font-bold">● {h.assumption}</span>
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
	);
};

export default CritiquePanel;

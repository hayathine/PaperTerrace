import type React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import CritiquePanel from "./CritiquePanel";
import DiscoverPanel from "./DiscoverPanel";
import SummaryPanel from "./SummaryPanel";

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
	const { t } = useTranslation();
	const [mode, setMode] = useState<Mode>("summary");

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

			<div
				className="flex-1 overflow-y-auto p-4 custom-scrollbar"
				style={{ WebkitOverflowScrolling: "touch" }}
			>
				{mode === "summary" && (
					<SummaryPanel
						sessionId={sessionId}
						paperId={paperId}
						isAnalyzing={isAnalyzing}
						isActive={isActive}
					/>
				)}
				{mode === "critique" && (
					<CritiquePanel sessionId={sessionId} paperId={paperId} />
				)}
				{mode === "discover" && <DiscoverPanel sessionId={sessionId} />}
			</div>
		</div>
	);
};

export default Summary;

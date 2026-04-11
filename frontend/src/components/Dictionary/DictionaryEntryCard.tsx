import type React from "react";
import { useTranslation } from "react-i18next";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";
import type { DictionaryEntryWithCoords } from "./Dictionary";

interface DictionaryEntryCardProps {
	entry: DictionaryEntryWithCoords;
	currentSubTab: "translation" | "explanation" | "figures" | "history";
	sessionId: string;
	savedItems: Set<string>;
	coordinates?: { page: number; x: number; y: number };
	onSave: (entry: DictionaryEntryWithCoords) => void;
	onDeepTranslate: (entry: DictionaryEntryWithCoords) => void;
	onAskInChat?: () => void;
	onJump?: (page: number, x: number, y: number, term?: string) => void;
}

const DictionaryEntryCard: React.FC<DictionaryEntryCardProps> = ({
	entry,
	currentSubTab,
	sessionId,
	savedItems,
	coordinates,
	onSave,
	onDeepTranslate,
	onAskInChat,
	onJump,
}) => {
	const { t } = useTranslation();

	return (
		<div
			className={`bg-white p-3 sm:p-4 rounded-xl border border-slate-100 shadow-sm animate-fade-in group transition-all hover:shadow-md relative overflow-hidden ${entry.is_analyzing ? "opacity-90" : ""}`}
		>
			{entry.is_analyzing && (
				<div className="absolute inset-0 z-50 bg-white/60 backdrop-blur-[1px] flex flex-col items-center justify-center animate-in fade-in duration-300">
					<div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mb-2" />
					<span className="text-[10px] font-bold text-orange-600 uppercase tracking-wider animate-pulse">
						{t("summary.processing")}
					</span>
				</div>
			)}

			<div className="flex justify-between items-start mb-3">
				<div className="text-sm font-semibold text-slate-800 leading-relaxed">
					{entry.word}
				</div>
				<div className="flex items-center gap-2">
					<CopyButton text={`${entry.word}\n${entry.translation}`} size={12} />
					<span
						className={`text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide ${
							entry.source === "Cache" || entry.source === "Gemini"
								? "bg-amber-100 text-amber-600"
								: entry.source === "LocalLM"
									? "bg-blue-100 text-blue-600"
									: "bg-gray-100"
						}`}
					>
						{entry.source}
					</span>
				</div>
			</div>

			{entry.image_url && (
				<div className="mb-4 rounded-xl overflow-hidden border border-slate-200">
					<img
						src={entry.image_url}
						alt="Figure"
						className="w-full h-auto object-contain bg-slate-50"
					/>
				</div>
			)}

			{currentSubTab === "explanation" && entry.source_translation && (
				<div className="mb-3 p-2.5 bg-blue-50 rounded-lg border border-blue-100">
					<p className="text-[9px] font-bold uppercase tracking-wider text-blue-400 mb-1">
						{t("viewer.dictionary.translation")}
					</p>
					<p className="text-xs text-blue-800 leading-relaxed font-medium">
						{entry.source_translation}
					</p>
				</div>
			)}

			<MarkdownContent className="prose prose-sm max-w-none text-sm text-slate-600 leading-relaxed font-medium mb-4">
				{entry.translation}
			</MarkdownContent>

			<div className="flex gap-2">
				<button
					type="button"
					onClick={() => onSave(entry)}
					disabled={savedItems.has(entry.word)}
					className={`flex-1 py-2.5 sm:py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 border ${
						savedItems.has(entry.word)
							? "bg-green-50 text-green-600 border-green-200 cursor-default"
							: "bg-slate-50 hover:bg-slate-100 text-slate-500 border-transparent group-hover:border-slate-200"
					}`}
				>
					{savedItems.has(entry.word) ? (
						<>
							<svg
								className="w-3 h-3"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth={2}
									d="M5 13l4 4L19 7"
								/>
							</svg>
							{t("viewer.dictionary.saved")}
						</>
					) : (
						<>
							<svg
								className="w-3 h-3"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth={2}
									d="M12 4v16m8-8H4"
								/>
							</svg>
							{t("viewer.dictionary.save_note")}
						</>
					)}
				</button>

				{entry.image_url ? (
					<button
						type="button"
						onClick={() => onAskInChat?.()}
						className="flex-1 py-2.5 sm:py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
					>
						<svg
							className="w-3.5 h-3.5"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
							/>
						</svg>
						<span>{t("viewer.dictionary.ask_in_chat")}</span>
					</button>
				) : (
					<button
						type="button"
						onClick={() => onDeepTranslate(entry)}
						className="flex-1 py-2.5 sm:py-2 bg-slate-50 hover:bg-slate-100 text-orange-600 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
					>
						<svg
							className="w-3.5 h-3.5"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
							/>
						</svg>
						<span>{t("viewer.dictionary.ask_ai")}</span>
					</button>
				)}

				{(onJump && entry.coords) || (onJump && coordinates) ? (
					<button
						type="button"
						onClick={() => {
							const c = entry.coords || coordinates;
							if (c && onJump) onJump(c.page, c.x, c.y, entry.word);
						}}
						className="px-3 py-2 bg-slate-50 hover:bg-slate-100 text-slate-500 rounded-lg text-xs font-bold transition-all flex items-center justify-center"
						title="Jump to Location"
					>
						JUMP
					</button>
				) : null}
			</div>

			<div className="mt-2 pl-1 pr-1">
				<FeedbackSection
					sessionId={sessionId}
					targetType="translation"
					targetId={entry.word}
					traceId={entry.trace_id}
				/>
			</div>
		</div>
	);
};

export default DictionaryEntryCard;

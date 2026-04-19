import type React from "react";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { usePaperCache } from "@/db/hooks";
import { useAuth } from "../../contexts/AuthContext";
import { useDictionaryFetch } from "../../hooks/useDictionaryFetch";
import { useDictionaryHistory } from "../../hooks/useDictionaryHistory";
import FigureInsight from "../FigureInsight/FigureInsight";
import type { SelectedFigure } from "../PDF/types";
import DictionaryEntryCard from "./DictionaryEntryCard";
import DictionaryHistoryTab from "./DictionaryHistoryTab";
import type { DictionaryEntry } from "./types";

export type DictionaryEntryWithCoords = DictionaryEntry & {
	coords?: { page: number; x: number; y: number };
	image_url?: string;
	is_analyzing?: boolean;
	source_translation?: string;
};

interface DictionaryProps {
	term?: string;
	sessionId: string;
	paperId?: string | null;
	context?: string;
	coordinates?: { page: number; x: number; y: number };
	conf?: number;
	onJump?: (page: number, x: number, y: number, term?: string) => void;
	imageUrl?: string;
	onAskInChat?: (prompt?: string) => void;
	onAskFigureInChat?: (figureId?: string | null) => void;
	selectedFigure?: SelectedFigure | null;
	subTab?: "translation" | "explanation" | "figures" | "history";
	onSubTabChange?: (
		tab: "translation" | "explanation" | "figures" | "history",
	) => void;
}

const Dictionary: React.FC<DictionaryProps> = ({
	term,
	sessionId,
	paperId,
	context,
	coordinates,
	conf,
	onJump,
	imageUrl,
	onAskInChat,
	onAskFigureInChat,
	selectedFigure,
	subTab = "translation",
	onSubTabChange,
}) => {
	const { t } = useTranslation();
	const { token } = useAuth();
	const { getCachedPaper } = usePaperCache();

	const currentSubTab = subTab || "translation";

	// IndexedDB からタイトルを事前取得（API の DB 参照を省略し翻訳速度を改善）
	const paperTitleRef = useRef<string | undefined>(undefined);
	useEffect(() => {
		if (!paperId) {
			paperTitleRef.current = undefined;
			return;
		}
		getCachedPaper(paperId).then((cached) => {
			paperTitleRef.current = cached?.title;
		});
	}, [paperId, getCachedPaper]);

	const {
		entries,
		explanationEntries,
		loading,
		error,
		isTruncated,
		handleDeepTranslate,
	} = useDictionaryFetch({
		term,
		sessionId,
		paperId,
		context,
		conf,
		imageUrl,
		currentSubTab,
		token,
		paperTitleRef,
		onSubTabChange,
	});

	const { savedNotes, savedItems, handleSaveToNote } = useDictionaryHistory({
		sessionId,
		paperId,
		token,
	});

	const isUrl =
		term &&
		!term.trim().includes(" ") &&
		!term.trim().includes("\n") &&
		(/^(https?:\/\/|\/\/|www\.)/i.test(term) || term.includes("doi.org/"));

	const activeEntries =
		currentSubTab === "explanation" ? explanationEntries : entries;

	let content: React.ReactNode;
	if (activeEntries.length === 0 && !loading && !error) {
		if (isUrl) {
			content = (
				<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
					<div className="bg-orange-50 p-4 rounded-xl mb-4 text-orange-400">
						<svg
							className="w-8 h-8"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
							/>
						</svg>
					</div>
					<p className="text-xs font-bold uppercase tracking-wider text-slate-400">
						{t("viewer.dictionary.external_link")}
					</p>
					<p className="text-[10px] mt-2 text-center text-slate-400 break-all max-w-[160px] sm:max-w-[200px]">
						{term}
					</p>
					<div className="flex flex-col gap-2 mt-6 w-full">
						<button
							type="button"
							onClick={() =>
								window.open(
									term.startsWith("//")
										? `https:${term}`
										: term.startsWith("www")
											? `https://${term}`
											: term,
									"_blank",
								)
							}
							className="w-full py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-xs font-bold transition-all"
						>
							{t("viewer.dictionary.open_link")}
						</button>
					</div>
				</div>
			);
		} else {
			content = (
				<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
					<div className="bg-slate-50 p-4 rounded-xl mb-4">
						<svg
							className="w-8 h-8 opacity-50"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
							/>
						</svg>
					</div>
					<p className="text-xs font-bold uppercase tracking-wider">
						{t("viewer.dictionary.ready")}
					</p>
					<p className="text-[10px] mt-2 text-center">
						{t("viewer.dictionary.click_hint")}
					</p>
				</div>
			);
		}
	} else {
		content = (
			<div
				className="p-4 flex-1 overflow-y-auto"
				style={{ WebkitOverflowScrolling: "touch" }}
			>
				{loading && activeEntries.length === 0 && (
					<div className="flex flex-col items-center justify-center py-12 animate-in fade-in duration-500">
						<div className="relative w-12 h-12 mb-4">
							<div className="absolute inset-0 rounded-full border-4 border-orange-100" />
							<div className="absolute inset-0 rounded-full border-4 border-orange-500 border-t-transparent animate-spin" />
						</div>
						<p className="text-sm font-bold text-slate-600 animate-pulse">
							{t("summary.processing")}
						</p>
						<p className="text-[10px] text-slate-400 mt-1">
							{t("common.loading_description")}
						</p>
					</div>
				)}

				{error && (
					<div className="text-xs text-red-400 bg-red-50 p-3 rounded-lg border border-red-100 mb-4">
						{error}
					</div>
				)}

				{isTruncated && !error && (
					<div className="text-xs text-amber-600 bg-amber-50 p-3 rounded-lg border border-amber-100 mb-4 flex items-start gap-2">
						<span className="mt-0.5 shrink-0">⚠</span>
						<span>
							{t(
								"viewer.dictionary.truncated_notice",
								"選択テキストが長すぎるため、先頭部分のみを翻訳しています。",
							)}
						</span>
					</div>
				)}

				<div className="space-y-4">
					{activeEntries.map((entry, index) => (
						<DictionaryEntryCard
							key={`${entry.word}-${index}`}
							entry={entry}
							currentSubTab={currentSubTab}
							sessionId={sessionId}
							savedItems={savedItems}
							coordinates={coordinates}
							onSave={(e) => handleSaveToNote(e, coordinates)}
							onDeepTranslate={handleDeepTranslate}
							onAskInChat={onAskInChat}
							onJump={onJump}
						/>
					))}
				</div>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-full overflow-hidden bg-white">
			{/* サブタブナビゲーション */}
			<div className="flex px-4 pt-2 border-b border-slate-100 bg-white sticky top-0 z-20 shrink-0 overflow-x-auto">
				{(
					[
						{
							key: "translation",
							label: t("sidebar.tabs.translation"),
							count: entries.length,
						},
						{
							key: "explanation",
							label: t("sidebar.tabs.explanation"),
							count: explanationEntries.length,
						},
						{ key: "figures", label: t("sidebar.tabs.figures"), count: 0 },
						{
							key: "history",
							label: t("sidebar.tabs.history"),
							count: savedNotes.length,
						},
					] as const
				).map(({ key, label, count }, i) => (
					<button
						key={key}
						type="button"
						onClick={() => onSubTabChange?.(key)}
						className={`${i > 0 ? "ml-6" : ""} pb-2 px-1 text-xs font-bold border-b-2 uppercase tracking-wider transition-all shrink-0 ${
							currentSubTab === key
								? "text-orange-600 border-orange-600"
								: "text-slate-400 hover:text-slate-600 border-transparent"
						}`}
					>
						{label} {count > 0 && `(${count})`}
					</button>
				))}
			</div>

			<div
				className="flex-1 overflow-y-auto"
				style={{ WebkitOverflowScrolling: "touch" }}
			>
				{currentSubTab === "translation" || currentSubTab === "explanation" ? (
					content
				) : currentSubTab === "history" ? (
					<div
						className="p-3 flex-1 overflow-y-auto"
						style={{ WebkitOverflowScrolling: "touch" }}
					>
						<DictionaryHistoryTab
							savedNotes={savedNotes}
							onSelectNote={() => onSubTabChange?.("translation")}
						/>
					</div>
				) : (
					<div className="p-4">
						<FigureInsight
							selectedFigure={selectedFigure}
							sessionId={sessionId}
							onAskInChat={onAskFigureInChat}
						/>
					</div>
				)}
			</div>
		</div>
	);
};

export default Dictionary;

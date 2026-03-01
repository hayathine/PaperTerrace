import type React from "react";
import { useTranslation } from "react-i18next";
import ChatWindow from "../Chat/ChatWindow";
import Dictionary from "../Dictionary/Dictionary";
import FigureInsight from "../FigureInsight/FigureInsight";
import NoteList from "../Notes/NoteList";
import RecommendationTab from "../Recommendation/RecommendationTab";
import Summary from "../Summary/Summary";

interface SidebarProps {
	sessionId: string;
	activeTab: string;
	onTabChange: (tab: string) => void;
	selectedWord?: string;
	context?: string;
	coordinates?: { page: number; x: number; y: number };
	conf?: number;
	selectedImage?: string;
	onJump?: (page: number, x: number, y: number, term?: string) => void;
	isAnalyzing?: boolean;
	paperId?: string | null;
	pendingFigureId?: string | null;
	onPendingFigureConsumed?: () => void;
	pendingChatPrompt?: string | null;
	onPendingChatConsumed?: () => void;
	onEvidenceClick?: (grounding: any) => void;
	onFigureExplain?: (figureId: string) => void;
	onClose?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
	sessionId,
	activeTab,
	onTabChange,
	selectedWord,
	context,
	coordinates,
	conf,
	selectedImage,
	onJump,
	isAnalyzing = false,
	paperId,
	pendingFigureId,
	onPendingFigureConsumed,
	pendingChatPrompt,
	onPendingChatConsumed,
	onEvidenceClick,
	onFigureExplain,
	onClose,
}) => {
	const { t } = useTranslation();

	const tabs = [
		{
			id: "dict",
			label: t("sidebar.tabs.dict"),
			icon: (
				<svg
					className="w-3.5 h-3.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
					/>
				</svg>
			),
		},
		{
			id: "summary",
			label: t("sidebar.tabs.summary"),
			icon: (
				<svg
					className="w-3.5 h-3.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
					/>
				</svg>
			),
		},
		{
			id: "chat",
			label: t("sidebar.tabs.chat"),
			icon: (
				<svg
					className="w-3.5 h-3.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
					/>
				</svg>
			),
		},
		{
			id: "notes",
			label: t("sidebar.tabs.notes"),
			icon: (
				<svg
					className="w-3.5 h-3.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
					/>
				</svg>
			),
		},
		{
			id: "figures",
			label: t("sidebar.tabs.figures"),
			icon: (
				<svg
					className="w-3.5 h-3.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
					/>
				</svg>
			),
		},
		{
			id: "explore",
			label: t("nav.explore"),
			icon: (
				<svg
					className="w-3.5 h-3.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeWidth="2"
						d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
					/>
				</svg>
			),
		},
	];

	return (
		<div className="flex flex-col h-full bg-white border-l border-slate-200 shadow-sm overflow-hidden font-sans">
			{/* Tab Navigation */}
			<div className="flex bg-slate-50 border-b border-slate-200 overflow-x-auto items-center pr-2">
				{tabs.map((tab) => (
					<button
						key={tab.id}
						type="button"
						onClick={() => onTabChange(tab.id)}
						className={`flex-1 min-w-[46px] sm:min-w-[52px] py-2 sm:py-2.5 flex flex-col items-center gap-1 transition-all border-b-2 ${
							activeTab === tab.id
								? "bg-white text-orange-500 border-orange-500"
								: "text-slate-400 border-transparent hover:text-slate-600"
						}`}
					>
						{tab.icon}
						<span className="text-[10px] sm:text-[11px] font-semibold leading-none">
							{tab.label}
						</span>
					</button>
				))}

				{onClose && (
					<button
						type="button"
						onClick={onClose}
						className="md:hidden ml-2 p-2 text-slate-400 hover:text-slate-600 shrink-0 border border-transparent hover:bg-slate-200 rounded-md transition-all"
						title={t("nav.close_panel", "Close panel")}
					>
						<svg
							className="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2.5"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
				)}
			</div>

			{/* Tab Content - All rendered but hidden when not active to preserve state */}
			<div className="flex-1 overflow-hidden relative">
				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "dict" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<Dictionary
						sessionId={sessionId}
						paperId={paperId}
						term={selectedWord}
						context={context}
						coordinates={coordinates}
						conf={conf}
						onJump={onJump}
						imageUrl={selectedImage}
						onAskInChat={() => onTabChange("chat")}
					/>
				</div>

				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "summary" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<Summary
						sessionId={sessionId}
						isAnalyzing={isAnalyzing}
						paperId={paperId}
					/>
				</div>

				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "chat" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<ChatWindow
						sessionId={sessionId}
						paperId={paperId}
						initialFigureId={pendingFigureId}
						onInitialChatSent={onPendingFigureConsumed}
						initialPrompt={pendingChatPrompt}
						onInitialPromptSent={onPendingChatConsumed}
						onEvidenceClick={onEvidenceClick}
					/>
				</div>

				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "notes" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<NoteList
						sessionId={sessionId}
						paperId={paperId}
						coordinates={coordinates}
						onJump={onJump}
						selectedContext={context}
						selectedTerm={selectedWord}
						selectedImage={selectedImage}
					/>
				</div>

				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "figures" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<FigureInsight
						paperId={paperId}
						onExplain={(figureId) => {
							onFigureExplain?.(figureId);
							onTabChange("chat");
						}}
					/>
				</div>

				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "explore" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<RecommendationTab sessionId={sessionId} />
				</div>
			</div>
		</div>
	);
};

export default Sidebar;

import type React from "react";
import { useTranslation } from "react-i18next";
import ChatWindow from "../Chat/ChatWindow";
import Dictionary from "../Dictionary/Dictionary";
import NoteList from "../Notes/NoteList";
import RecommendationTab from "../Recommendation/RecommendationTab";
import Summary from "../Summary/Summary";
import PaperStack from "./PaperStack";

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
	stackedPapers: { url: string; title?: string; addedAt: number }[];
	onStackPaper: (url: string, title?: string) => void;
	onRemoveFromStack: (url: string) => void;
	onEvidenceClick?: (grounding: any) => void;
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
	stackedPapers,
	onStackPaper,
	onRemoveFromStack,
	onEvidenceClick,
	onClose,
}) => {
	const { t } = useTranslation();

	return (
		<div className="flex flex-col h-full bg-white border-l border-slate-200 shadow-sm overflow-hidden font-sans">
			{/* Tab Navigation */}
			<div className="flex bg-slate-50 border-b border-slate-200 overflow-x-auto items-center pr-2">
				<button
					type="button"
					onClick={() => onTabChange("dict")}
					className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${
						activeTab === "dict"
							? "bg-white text-orange-500 border-orange-500 shadow-none"
							: "text-slate-400 border-transparent hover:text-slate-600"
					}`}
				>
					{t("sidebar.tabs.dict")}
				</button>

				<button
					type="button"
					onClick={() => onTabChange("summary")}
					className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${
						activeTab === "summary"
							? "bg-white text-orange-500 border-orange-500 shadow-none"
							: "text-slate-400 border-transparent hover:text-slate-600"
					}`}
				>
					{t("sidebar.tabs.summary")}
				</button>

				<button
					type="button"
					onClick={() => onTabChange("chat")}
					className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${
						activeTab === "chat"
							? "bg-white text-orange-500 border-orange-500 shadow-none"
							: "text-slate-400 border-transparent hover:text-slate-600"
					}`}
				>
					{t("sidebar.tabs.chat")}
				</button>

				<button
					type="button"
					onClick={() => onTabChange("notes")}
					className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${
						activeTab === "notes"
							? "bg-white text-orange-500 border-orange-500 shadow-none"
							: "text-slate-400 border-transparent hover:text-slate-600"
					}`}
				>
					{t("sidebar.tabs.notes")}
				</button>

				<button
					type="button"
					onClick={() => onTabChange("stack")}
					className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${
						activeTab === "stack"
							? "bg-white text-orange-500 border-orange-500 shadow-none"
							: "text-slate-400 border-transparent hover:text-slate-600"
					}`}
				>
					{t("sidebar.tabs.stack")}
				</button>

				<button
					type="button"
					onClick={() => onTabChange("explore")}
					className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 flex items-center justify-center gap-1 ${
						activeTab === "explore"
							? "bg-white text-amber-600 border-amber-600 shadow-none"
							: "text-slate-400 border-transparent hover:text-amber-600"
					}`}
					title="Explore Recommendations"
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
							strokeWidth="2.5"
							d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
						/>
					</svg>
					{t("nav.explore")}
				</button>

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
						onStackPaper={onStackPaper}
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
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "stack" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<PaperStack papers={stackedPapers} onRemove={onRemoveFromStack} />
				</div>

				<div
					className={`absolute inset-0 bg-white transition-opacity duration-200 ${activeTab === "explore" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
				>
					<RecommendationTab
						sessionId={sessionId}
						onStackPaper={onStackPaper}
					/>
				</div>
			</div>
		</div>
	);
};

export default Sidebar;

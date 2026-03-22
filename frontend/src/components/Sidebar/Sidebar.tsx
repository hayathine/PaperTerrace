import { lazy, Suspense, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Grounding } from "../Chat/types";
import type { SelectedFigure } from "../PDF/types";

const ChatWindow = lazy(() => import("../Chat/ChatWindow"));
const Dictionary = lazy(() => import("../Dictionary/Dictionary"));
const NoteList = lazy(() => import("../Notes/NoteList"));
const Summary = lazy(() => import("../Summary/Summary"));

const TabFallback = () => (
	<div className="flex items-center justify-center h-full">
		<div className="w-5 h-5 border-2 border-orange-400 border-t-transparent rounded-full animate-spin" />
	</div>
);

interface SidebarProps {
	sessionId: string;
	activeTab: string;
	onTabChange: (tab: string) => void;
	dictSubTab?: "translation" | "explanation" | "figures" | "history";
	onDictSubTabChange?: (
		tab: "translation" | "explanation" | "figures" | "history",
	) => void;
	selectedWord?: string;
	context?: string;
	coordinates?: { page: number; x: number; y: number };
	conf?: number;
	selectedImage?: string;
	onJump?: (page: number, x: number, y: number, term?: string) => void;
	isAnalyzing?: boolean;
	paperId?: string | null;
	selectedFigure?: SelectedFigure | null;
	pendingFigureId?: string | null;
	onPendingFigureConsumed?: () => void;
	pendingChatPrompt?: string | null;
	onPendingChatConsumed?: () => void;
	onEvidenceClick?: (grounding: Grounding) => void;
	onClose?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
	sessionId,
	activeTab,
	onTabChange,
	dictSubTab = "translation",
	onDictSubTabChange,
	selectedWord,
	context,
	coordinates,
	conf,
	selectedImage,
	onJump,
	isAnalyzing = false,
	paperId,
	selectedFigure,
	pendingFigureId,
	onPendingFigureConsumed,
	pendingChatPrompt,
	onPendingChatConsumed,
	onEvidenceClick,
	onClose,
}) => {
	const { t } = useTranslation();

	const tabs = useMemo(
		() => [
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
				id: "analysis",
				label: t("sidebar.tabs.analysis"),
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
							d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
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
				id: "comments",
				label: t("sidebar.tabs.comments"),
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
							d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"
						/>
					</svg>
				),
			},
		],
		[t],
	);

	return (
		<div className="flex flex-col h-full bg-white border-l border-slate-200 shadow-sm overflow-hidden font-sans">
			{/* Tab Navigation:
			    ×ボタンは overflow-x-auto コンテナの外に配置する。
			    overflow-x-auto 内のタッチイベントは pan-x として解釈されるため、
			    同一コンテナ内のボタンの click が発火しない問題を防ぐ。 */}
			<div className="flex bg-slate-50 border-b border-slate-200 items-center">
				<div
					className="flex flex-1 overflow-x-auto"
					style={{ touchAction: "pan-x" }}
				>
					{tabs.map((tab) => (
						<button
							key={tab.id}
							type="button"
							onClick={() => onTabChange(tab.id)}
							className={`shrink-0 min-w-[52px] sm:min-w-[60px] py-2 sm:py-2.5 flex flex-col items-center gap-1 transition-all border-b-2 ${
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
				</div>

				{onClose && (
					<button
						type="button"
						onClick={onClose}
						className="md:hidden mx-2 p-2 text-slate-400 hover:text-slate-600 shrink-0 border border-transparent hover:bg-slate-200 rounded-md transition-all"
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
					className={`absolute inset-0 overflow-y-auto bg-white transition-opacity duration-200 ${activeTab === "notes" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
					style={{ touchAction: "pan-y" }}
				>
					<Suspense fallback={<TabFallback />}>
						<Dictionary
							sessionId={sessionId}
							paperId={paperId}
							subTab={dictSubTab}
							onSubTabChange={onDictSubTabChange}
							term={selectedWord}
							context={context}
							coordinates={coordinates}
							conf={conf}
							onJump={onJump}
							imageUrl={selectedImage}
							onAskInChat={() => onTabChange("chat")}
							selectedFigure={selectedFigure}
						/>
					</Suspense>
				</div>

				<div
					className={`absolute inset-0 overflow-y-auto bg-white transition-opacity duration-200 ${activeTab === "analysis" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
					style={{ touchAction: "pan-y" }}
				>
					<Suspense fallback={<TabFallback />}>
						<Summary
							sessionId={sessionId}
							isAnalyzing={isAnalyzing}
							paperId={paperId}
							isActive={activeTab === "analysis"}
						/>
					</Suspense>
				</div>

				<div
					className={`absolute inset-0 overflow-y-auto bg-white transition-opacity duration-200 ${activeTab === "chat" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
					style={{ touchAction: "pan-y" }}
				>
					<Suspense fallback={<TabFallback />}>
						<ChatWindow
							sessionId={sessionId}
							paperId={paperId}
							initialFigureId={pendingFigureId}
							onInitialChatSent={onPendingFigureConsumed}
							initialPrompt={pendingChatPrompt}
							onInitialPromptSent={onPendingChatConsumed}
							onEvidenceClick={onEvidenceClick}
						/>
					</Suspense>
				</div>

				<div
					className={`absolute inset-0 overflow-y-auto bg-white transition-opacity duration-200 ${activeTab === "comments" ? "opacity-100 z-10 pointer-events-auto" : "opacity-0 z-0 pointer-events-none"}`}
					style={{ touchAction: "pan-y" }}
				>
					<Suspense fallback={<TabFallback />}>
						<NoteList
							sessionId={sessionId}
							paperId={paperId}
							coordinates={coordinates}
							onJump={onJump}
							selectedContext={context}
							selectedTerm={selectedWord}
							selectedImage={selectedImage}
						/>
					</Suspense>
				</div>
			</div>
		</div>
	);
};

export default Sidebar;

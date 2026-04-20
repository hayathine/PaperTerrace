import type React from "react";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import type { Grounding } from "../Chat/types";
import PDFPage from "./PDFPage";
import TextModeViewer from "./TextModeViewer";
import type { PageData, SelectedFigure } from "./types";
import { usePDFViewerLogic } from "./usePDFViewerLogic";

export interface PDFViewerProps {
	taskId?: string;
	initialData?: PageData[];
	uploadFile?: File | null;
	sessionId?: string;
	onWordClick?: (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
		conf?: number,
	) => void;
	onTextSelect?: (
		text: string,
		coords: { page: number; x: number; y: number },
	) => void;
	onAreaSelect?: (
		imageUrl: string,
		coords: { page: number; x: number; y: number },
	) => void;
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
	onStatusChange?: (
		status:
			| "idle"
			| "uploading"
			| "processing"
			| "layout_analysis"
			| "done"
			| "error",
	) => void;
	onPaperLoaded?: (paperId: string | null) => void;
	onAskAI?: (
		prompt: string,
		imageUrl?: string,
		coords?: { page: number; x: number; y: number },
		originalText?: string,
		contextText?: string,
	) => void;
	onFigureSelect?: (figure: SelectedFigure) => void;
	paperId?: string | null;
	// 検索関連props
	searchTerm?: string;
	onSearchMatchesUpdate?: (
		matches: Array<{ page: number; wordIndex: number }>,
	) => void;
	currentSearchMatch?: { page: number; wordIndex: number } | null;
	evidence?: Grounding;
	appEnv?: string;
	maxPdfSize?: number;
	mode?: "text" | "stamp" | "area" | "plaintext";
}

const PDFViewer: React.FC<PDFViewerProps> = ({
	uploadFile,
	paperId: propPaperId,
	sessionId,
	onWordClick,
	onTextSelect,
	jumpTarget,
	onStatusChange,
	onPaperLoaded,
	onAskAI,
	onFigureSelect,
	searchTerm,
	onSearchMatchesUpdate,
	currentSearchMatch,
	evidence,
	appEnv = "prod",
	maxPdfSize = 50,
	mode: externalMode,
}) => {
	const { t } = useTranslation();
	const isLocal = appEnv === "local" || appEnv === "staging";

	// --- 状態と副作用を usePDFViewerLogic に移譲 ---
	const {
		pages,
		pagesWithLines,
		status,
		errorMsg,
		uploadProgress,
		loadedPaperId,
		loadedPaperTitle,
		hasMountedPdfMode,
		mode,
		evidenceHighlights,
		handlePageVisible,
	} = usePDFViewerLogic({
		uploadFile,
		paperId: propPaperId,
		sessionId,
		onStatusChange,
		onPaperLoaded,
		searchTerm,
		onSearchMatchesUpdate,
		currentSearchMatch,
		evidence,
		maxPdfSize,
		mode: externalMode,
		jumpTarget,
	});

	// Handler helpers that are strictly UI callback logic
	const handleWordClick = useCallback(
		(
			word: string,
			context?: string,
			coords?: { page: number; x: number; y: number },
			conf?: number,
		) => {
			if (onWordClick) {
				onWordClick(word, context, coords, conf);
			}
		},
		[onWordClick],
	);

	const handleTextSelect = useCallback(
		(text: string, coords: { page: number; x: number; y: number }) => {
			if (onTextSelect) {
				onTextSelect(text, coords);
			}
		},
		[onTextSelect],
	);

	return (
		<div className="w-full max-w-5xl mx-auto p-2 md:p-4 relative min-h-full pb-20">
			{/* Non-blocking status indicators */}
			{(status === "uploading" ||
				status === "processing" ||
				status === "layout_analysis") && (
				<div className="fixed bottom-4 right-4 z-50 bg-white rounded-full shadow-lg p-3 border border-orange-200">
					<div className="flex items-center gap-2">
						<div className="animate-spin rounded-full h-4 w-4 border-2 border-orange-200 border-t-orange-600"></div>
						<span className="text-xs text-orange-600 font-medium">
							{status === "uploading"
								? t("viewer.uploading_pdf")
								: status === "layout_analysis"
									? "構造化解析中..."
									: "読み込み中..."}
						</span>
					</div>
				</div>
			)}

			{/* Initial state - no PDF loaded */}
			{status === "idle" &&
				!uploadFile &&
				!propPaperId &&
				pages.length === 0 && (
					<div className="text-center p-10 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
						{t("viewer.waiting_pdf")}
					</div>
				)}

			{/* Processing with no pages yet - show friendly message */}
			{(status === "uploading" || status === "processing") &&
				pages.length === 0 && (
					<div className="text-center p-10 text-gray-400">
						<div className="text-4xl mb-4">📄</div>
						<p className="text-sm">
							{status === "uploading"
								? t("viewer.uploading_pdf")
								: "PDFを処理中..."}
						</p>
						{status === "uploading" && uploadProgress > 0 && (
							<div className="w-full max-w-xs mx-auto mt-3">
								<div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
									<div
										className="h-full bg-indigo-500 transition-all duration-200"
										style={{ width: `${uploadProgress}%` }}
									/>
								</div>
								<p className="text-xs text-slate-400 mt-1">
									{t("viewer.uploading_progress", { percent: uploadProgress })}
								</p>
							</div>
						)}
						<p className="text-xs mt-2 text-gray-300">
							このまま他の操作を続けることができます
						</p>
					</div>
				)}

			{status === "error" && (
				<div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
					Error: {errorMsg}
				</div>
			)}

			{/* Content Area - Show as soon as we have pages */}
			{pages.length > 0 && (
				<>
					{/* TextMode: 初期状態からマウント。CSS display で高速切り替え */}
					<div className={mode === "plaintext" ? "block" : "hidden"}>
						<TextModeViewer
							pages={pagesWithLines}
							paperId={loadedPaperId}
							paperTitle={loadedPaperTitle}
							onWordClick={handleWordClick}
							onTextSelect={handleTextSelect}
							onAskAI={onAskAI}
							searchTerm={searchTerm}
							jumpTarget={mode === "plaintext" ? jumpTarget : null}
							onPageVisible={handlePageVisible}
						/>
					</div>

					{/* PDF グリッド: 初回アクセス時に初めてマウント（遅延マウント）。
					     以降は CSS display トグルで再マウントコストなしに切り替え */}
					{hasMountedPdfMode && (
						<div className={mode !== "plaintext" ? "block" : "hidden"}>
							{/* group/viewer + data-click-mode で CSS バリアント (group-data-[click-mode]/viewer:*)
							    を制御。isClickMode を prop として渡さないことで、モード切り替え時に
							    全 PDFPage が再レンダーされるのを防ぐ。 */}
							<div
								className="space-y-6 group/viewer"
								data-click-mode={mode === "text" ? "" : undefined}
							>
								{pages.map((page) => (
									<PDFPage
										key={`${loadedPaperId ?? "upload"}-${page.page_num}`}
										page={page}
										onWordClick={handleWordClick}
										onTextSelect={handleTextSelect}
										onAskAI={onAskAI}
										onFigureSelect={onFigureSelect}
										jumpTarget={jumpTarget}
										searchTerm={searchTerm}
										currentSearchMatch={currentSearchMatch}
										evidenceHighlights={evidenceHighlights[page.page_num]}
										isLocal={isLocal}
										onPageVisible={handlePageVisible}
									/>
								))}
							</div>
						</div>
					)}
				</>
			)}
		</div>
	);
};

export default PDFViewer;

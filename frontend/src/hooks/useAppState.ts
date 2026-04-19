import type React from "react";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import type { SelectedFigure } from "../components/PDF/types";
import { useAuth } from "../contexts/AuthContext";
import { useLoading } from "../contexts/LoadingContext";
import { usePaperCache } from "../db/hooks";
import { useSyncStatus } from "../db/sync";
import { syncTrajectory } from "../lib/recommendation";
import { clampWidth, useLayoutState } from "./useLayoutState";
import { usePaperLibrary } from "./usePaperLibrary";
import { usePaperLifecycle } from "./usePaperLifecycle";
import { usePinchZoom } from "./usePinchZoom";
import { useScrollTracking } from "./useScrollTracking";
import { useSearchState } from "./useSearchState";
import { useServiceHealth } from "./useServiceHealth";
import { useWordInteraction } from "./useWordInteraction";

const log = createLogger("useAppState");

/**
 * App コンポーネントのすべてのロジックを集約したカスタムフック。
 * UI（JSX）は App.tsx に残し、状態管理・副作用・ハンドラはここで一元管理する。
 */
export function useAppState() {
	const { user, isGuest, logout, token } = useAuth();
	const navigate = useNavigate();
	const { t } = useTranslation();
	const { startLoading, stopLoading } = useLoading();
	const {
		isHealthy,
		isMaintenance,
		message: healthMessage,
		reportFailure,
	} = useServiceHealth(!isGuest && !!API_URL);

	const [uploadFile, setUploadFile] = useState<File | null>(null);
	const [currentPaperId, setCurrentPaperId] = useState<string | null>(null);
	const [isAnalyzing, setIsAnalyzing] = useState(false);

	// Session ID
	const [sessionId] = useState(() => {
		const saved = localStorage.getItem("paper_terrace_session");
		if (saved) return saved;
		const newId = `session-${Math.random().toString(36).substring(2, 11)}`;
		localStorage.setItem("paper_terrace_session", newId);
		return newId;
	});

	const [activeTab, setActiveTab] = useState("chat");
	const [dictSubTab, setDictSubTab] = useState<
		"translation" | "explanation" | "figures" | "history"
	>("translation");
	const [showLoginModal, setShowLoginModal] = useState(false);

	// Layout
	const {
		sidebarWidth,
		setSidebarWidth,
		isResizing,
		setIsResizing,
		isLeftSidebarOpen,
		setIsLeftSidebarOpen,
		isRightSidebarOpen,
		setIsRightSidebarOpen,
		isMobile,
	} = useLayoutState();

	// Paper library
	const { uploadedPapers, isPapersLoading, refreshPapers, deletePaper } =
		usePaperLibrary({ userId: user?.id, token, isGuest });

	// Word/text/area interaction state
	const {
		translationWord,
		translationContext,
		translationCoordinates,
		translationConf,
		explanationWord,
		explanationContext,
		explanationCoordinates,
		selectedWord,
		selectedContext,
		selectedCoordinates,
		selectedImage,
		jumpTarget,
		setJumpTarget,
		pendingFigureId,
		setPendingFigureId,
		pendingChatPrompt,
		setPendingChatPrompt,
		selectedFigure,
		setSelectedFigure,
		activeEvidence,
		setActiveEvidence,
		resetWordState,
		setTranslation,
		setTextSelection,
		setAreaSelection,
		setExplanation,
	} = useWordInteraction();

	// Paper lifecycle (cache delete + duration tracking)
	usePaperLifecycle(currentPaperId, sessionId, token);

	// Guest → signed-in transition detection
	const prevUserRef = useRef<typeof user | undefined>(undefined);
	const { getCachedPaper } = usePaperCache();

	const handleScroll = useScrollTracking(currentPaperId || uploadFile?.name);
	const {
		zoom,
		resetZoom,
		zoomIn,
		zoomOut,
		containerRef: zoomContainerRef,
		onWheel: handleZoomWheel,
	} = usePinchZoom();

	const [appEnv, setAppEnv] = useState<string>("prod");
	const [maxPdfSize, setMaxPdfSize] = useState<number>(50);
	const [pdfMode, setPdfMode] = useState<
		"text" | "stamp" | "area" | "plaintext"
	>("plaintext");
	const [isModeTransitionPending, startModeTransition] = useTransition();
	const syncStatus = useSyncStatus();

	// Config fetch with cold-start retry
	useEffect(() => {
		const fetchConfig = async () => {
			for (let attempt = 0; attempt < 3; attempt++) {
				try {
					const res = await fetch(`${API_URL}/api/config`, {
						signal: AbortSignal.timeout(10000),
					});
					const data = await res.json();
					if (data?.app_env) setAppEnv(data.app_env);
					if (data?.max_pdf_size_mb) setMaxPdfSize(data.max_pdf_size_mb);
					return;
				} catch (err) {
					if (attempt < 2) {
						await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
					} else {
						log.error("fetch_config", "Failed to fetch config", { error: err });
						reportFailure(503);
					}
				}
			}
		};
		fetchConfig();
	}, []);

	// Document title
	useEffect(() => {
		if (appEnv === "local") {
			document.title = `PaperTerrace (Local) - ${t("tagline", "Read papers casually, like sitting on a terrace")}`;
		} else {
			document.title = `PaperTerrace - ${t("tagline", "Read papers casually, like sitting on a terrace")}`;
		}
	}, [t, appEnv]);

	// Guest → logged-in transition: claim paper
	useEffect(() => {
		const prevUser = prevUserRef.current;
		prevUserRef.current = user;

		if (prevUser === null && user && token && currentPaperId) {
			const claimGuestPaper = async () => {
				const cached = await getCachedPaper(currentPaperId);
				if (!cached) return;

				try {
					const res = await fetch(`${API_URL}/api/papers/claim`, {
						method: "POST",
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${token}`,
						},
						body: JSON.stringify({
							paper_id: cached.id,
							file_hash: cached.file_hash,
							filename: cached.title,
							ocr_text: cached.ocr_text ?? "",
							layout_json: cached.layout_json ?? null,
						}),
					});

					if (res.ok) {
						await refreshPapers();
					}
				} catch (err) {
					log.error("claim_paper", "ゲスト論文のクレームに失敗しました", {
						error: err,
					});
				}
			};
			claimGuestPaper();
		}
	}, [user, token, currentPaperId]);

	// ---- Handlers ----

	const handlePaperLoaded = (paperId: string | null) => {
		if (paperId) {
			setCurrentPaperId(paperId);
			setUploadFile(null);
			setIsRightSidebarOpen(true);
		}
		if (paperId && !uploadedPapers.some((p) => p?.paper_id === paperId)) {
			refreshPapers();
		}
	};

	const handlePaperSelect = (paper: {
		paper_id: string;
		[key: string]: unknown;
	}) => {
		setUploadFile(null);
		setCurrentPaperId(paper.paper_id);
		setIsRightSidebarOpen(true);
	};

	const handleDeletePaper = async (
		e: React.MouseEvent,
		paper: { paper_id: string; [key: string]: unknown },
	) => {
		e.stopPropagation();
		if (!window.confirm(t("common.confirm_delete"))) return;
		const wasCurrentPaper = await deletePaper(paper, currentPaperId, user);
		if (wasCurrentPaper) setCurrentPaperId(null);
	};

	const handleDirectFileSelect = (file: File) => {
		setUploadFile(file);
		setCurrentPaperId(null);
		resetWordState();
		setActiveTab("chat");
		setDictSubTab("translation");
	};

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		if (e.target.files?.[0]) {
			handleDirectFileSelect(e.target.files[0]);
		}
	};

	const handleWordClick = (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
		conf?: number,
	) => {
		if (currentPaperId) {
			syncTrajectory(
				{
					session_id: sessionId,
					paper_id: currentPaperId,
					word_clicks: [
						{
							word,
							context: context || "",
							section: "Unknown",
							timestamp: Date.now() / 1000,
						},
					],
				},
				token,
			);
		}

		setTranslation(word, context, coords, conf);
		setActiveTab("notes");
		setDictSubTab("translation");
		setIsRightSidebarOpen(true);
	};

	const handleTextSelect = (
		text: string,
		coords: { page: number; x: number; y: number },
	) => {
		setTextSelection(text, coords);
		setActiveTab("comments");
		setIsRightSidebarOpen(true);
	};

	const handleAreaSelect = (
		imageUrl: string,
		coords: { page: number; x: number; y: number },
	) => {
		setAreaSelection(imageUrl, coords);
		setActiveTab("comments");
		setIsRightSidebarOpen(true);
	};

	const handleJumpToLocation = (
		page: number,
		x: number,
		y: number,
		term?: string,
	) => {
		setJumpTarget({ page, x, y, term });
	};

	const handleAnalysisStatusChange = useCallback(
		(status: string) => {
			if (status === "uploading") {
				setIsAnalyzing(true);
				startLoading(t("viewer.uploading_pdf"));
			} else if (status === "processing") {
				setIsAnalyzing(true);
				startLoading(t("viewer.processing_pdf"));
			} else if (status === "layout_analysis") {
				setIsAnalyzing(true);
				startLoading(t("viewer.analyzing_layout"));
			} else {
				setIsAnalyzing(false);
				stopLoading();
			}
		},
		[startLoading, stopLoading, t],
	);

	const handleAskAI = (
		prompt: string,
		imageUrl?: string,
		coords?: { page: number; x: number; y: number },
		originalText?: string,
		contextText?: string,
	) => {
		if (imageUrl) {
			setAreaSelection(imageUrl, coords ?? { page: 0, x: 0, y: 0 });
			setActiveTab("notes");
			setDictSubTab("figures");
			setIsRightSidebarOpen(true);
		} else {
			setExplanation(originalText || prompt, contextText, coords);
			setActiveTab("notes");
			setDictSubTab("explanation");
			setIsRightSidebarOpen(true);
		}
	};

	const handleFigureSelect = (figure: SelectedFigure) => {
		setSelectedFigure(figure);
		setActiveTab("notes");
		setDictSubTab("figures");
		setIsRightSidebarOpen(true);
	};

	// Search state
	const {
		isSearchOpen,
		searchTerm,
		setSearchTerm,
		searchMatches,
		currentMatchIndex,
		currentSearchMatch,
		handleNextMatch,
		handlePrevMatch,
		handleCloseSearch,
		handleSearchMatchesUpdate,
	} = useSearchState(!!(uploadFile || currentPaperId));

	const handleResizeKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "ArrowLeft") {
			setSidebarWidth((w: number) =>
				clampWidth(w - 10, window.innerWidth, isLeftSidebarOpen),
			);
		} else if (e.key === "ArrowRight") {
			setSidebarWidth((w: number) =>
				clampWidth(w + 10, window.innerWidth, isLeftSidebarOpen),
			);
		}
	};

	return {
		// Auth
		user,
		isGuest,
		logout,
		token,
		navigate,
		t,
		// Health
		isHealthy,
		isMaintenance,
		healthMessage,
		// File / Paper
		uploadFile,
		currentPaperId,
		isAnalyzing,
		uploadedPapers,
		isPapersLoading,
		// Session / Tabs
		sessionId,
		activeTab,
		setActiveTab,
		dictSubTab,
		setDictSubTab,
		showLoginModal,
		setShowLoginModal,
		// Layout
		sidebarWidth,
		setSidebarWidth,
		isResizing,
		setIsResizing,
		isLeftSidebarOpen,
		setIsLeftSidebarOpen,
		isRightSidebarOpen,
		setIsRightSidebarOpen,
		isMobile,
		// Word interaction state
		translationWord,
		translationContext,
		translationCoordinates,
		translationConf,
		explanationWord,
		explanationContext,
		explanationCoordinates,
		selectedWord,
		selectedContext,
		selectedCoordinates,
		selectedImage,
		jumpTarget,
		pendingFigureId,
		setPendingFigureId,
		pendingChatPrompt,
		setPendingChatPrompt,
		selectedFigure,
		activeEvidence,
		setActiveEvidence,
		// Zoom
		zoom,
		resetZoom,
		zoomIn,
		zoomOut,
		zoomContainerRef,
		handleZoomWheel,
		// Scroll
		handleScroll,
		// Config / Mode
		appEnv,
		maxPdfSize,
		pdfMode,
		setPdfMode,
		isModeTransitionPending,
		startModeTransition,
		syncStatus,
		// Search
		isSearchOpen,
		searchTerm,
		setSearchTerm,
		searchMatches,
		currentMatchIndex,
		currentSearchMatch,
		handleNextMatch,
		handlePrevMatch,
		handleCloseSearch,
		handleSearchMatchesUpdate,
		// Handlers
		handlePaperLoaded,
		handlePaperSelect,
		handleDeletePaper,
		handleDirectFileSelect,
		handleFileChange,
		handleWordClick,
		handleTextSelect,
		handleAreaSelect,
		handleJumpToLocation,
		handleAnalysisStatusChange,
		handleAskAI,
		handleFigureSelect,
		handleResizeKeyDown,
	};
}

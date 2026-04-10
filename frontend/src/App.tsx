import type React from "react";
import {
	lazy,
	Suspense,
	useCallback,
	useEffect,
	useRef,
	useState,
	useTransition,
} from "react";
import { useTranslation } from "react-i18next";
import { Route, Routes, useNavigate } from "react-router-dom";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import Login from "./components/Auth/Login";
import RequestForm from "./components/Contact/RequestForm";
import ErrorBoundary from "./components/Error/ErrorBoundary";
import PDFViewer from "./components/PDF/PDFViewer";
import type { SelectedFigure } from "./components/PDF/types";
import SearchBar from "./components/Search/SearchBar";
import Sidebar from "./components/Sidebar/Sidebar";
import GlobalLoading from "./components/UI/GlobalLoading";
import ServiceOutage from "./components/UI/ServiceOutage";
import UploadScreen from "./components/Upload/UploadScreen";
import { useAuth } from "./contexts/AuthContext";
import { useLoading } from "./contexts/LoadingContext";

const Dashboard = lazy(() => import("./pages/Dashboard"));

import { usePaperCache } from "./db/hooks";
import { useSyncStatus } from "./db/sync";
import { clampWidth, useLayoutState } from "./hooks/useLayoutState";
import { usePaperLibrary } from "./hooks/usePaperLibrary";
import { usePaperLifecycle } from "./hooks/usePaperLifecycle";
import { usePinchZoom } from "./hooks/usePinchZoom";
import { useScrollTracking } from "./hooks/useScrollTracking";
import { useSearchState } from "./hooks/useSearchState";
import { useServiceHealth } from "./hooks/useServiceHealth";
import { useWordInteraction } from "./hooks/useWordInteraction";
import { syncTrajectory } from "./lib/recommendation";

const log = createLogger("App");

function App() {
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

	// Sidebar State
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

	// 論文一覧管理
	const { uploadedPapers, isPapersLoading, refreshPapers, deletePaper } =
		usePaperLibrary({ userId: user?.id, token, isGuest });

	// 翻訳・解説・選択テキスト管理
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

	// Context Cache ライフサイクル管理
	usePaperLifecycle(currentPaperId, sessionId, token);

	// サインイン遷移検知用（null = ゲスト確定、undefined = 初回レンダリング前）
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

	useEffect(() => {
		// コールドスタート対策: 最大3回リトライ（2s, 4s インターバル）
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

	useEffect(() => {
		if (appEnv === "local") {
			document.title = `PaperTerrace (Local) - ${t("tagline", "Read papers casually, like sitting on a terrace")}`;
		} else {
			document.title = `PaperTerrace - ${t("tagline", "Read papers casually, like sitting on a terrace")}`;
		}
	}, [t, appEnv]);

	// ゲスト → サインイン遷移を検知し、表示中の論文をライブラリに保存する
	useEffect(() => {
		const prevUser = prevUserRef.current;
		prevUserRef.current = user;

		// prevUser === null: ゲスト確定状態からサインインした場合のみ実行
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

	const handlePaperLoaded = (paperId: string | null) => {
		if (paperId) {
			setCurrentPaperId(paperId);
			setUploadFile(null);
			setIsRightSidebarOpen(true);
		}
		// 新規論文の場合は一覧を再取得
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
			// 選択 word だけ上書き（Figure 用ラベルより prompt を優先）
			setActiveTab("notes");
			setDictSubTab("figures");
			setIsRightSidebarOpen(true);
		} else {
			// テキスト解説：解説専用 state のみ更新（翻訳 state は変更しない）
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

	// 検索状態
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

	return (
		<Routes>
			<Route
				path="/dashboard"
				element={
					<Suspense
						fallback={
							<div className="flex items-center justify-center h-screen">
								<div className="animate-spin w-8 h-8 rounded-full border-4 border-orange-600 border-t-transparent" />
							</div>
						}
					>
						<Dashboard />
					</Suspense>
				}
			/>
			<Route
				path="/*"
				element={
					<ErrorBoundary>
						<div className="flex h-screen h-dvh w-full bg-gray-100 overflow-hidden">
							{/* Mobile Backdrop for Left Sidebar */}
							{isLeftSidebarOpen && (
								<button
									type="button"
									className="fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity w-full h-full border-none p-0 cursor-default"
									onClick={() => setIsLeftSidebarOpen(false)}
									aria-label="Close left sidebar"
								/>
							)}

							{/* Left Sidebar
			    モバイルでは fixed 配置にしてドキュメント幅に影響させない。
			    absolute だと overflow:hidden でクリップされずに横スクロールが発生するため。 */}
							<div
								className={`bg-white text-slate-900 border-r border-slate-200 transition-all duration-300 ease-in-out flex flex-col shrink-0 fixed top-0 left-0 md:relative md:top-auto md:left-auto z-50 h-screen h-dvh md:h-full ${
									isLeftSidebarOpen
										? "w-72 md:w-64 translate-x-0"
										: "-translate-x-full md:translate-x-0 w-72 md:w-0 overflow-hidden"
								}`}
							>
								<div className="w-full p-4 flex flex-col h-full">
									<div className="flex items-center gap-3 mb-8">
										<button
											type="button"
											onClick={() => setIsLeftSidebarOpen(false)}
											className="p-2 rounded-xl bg-slate-50 text-slate-400 hover:bg-orange-500 hover:text-white transition-all duration-300 shadow-sm border border-slate-200 hover:border-orange-400"
											title={t("nav.close_menu")}
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
													strokeWidth="3"
													d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
												/>
											</svg>
										</button>
										<h1 className="text-xl font-bold">PaperTerrace</h1>
									</div>
									<div className="flex-1 overflow-y-auto px-2 mt-4 custom-scrollbar">
										<p className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-4 px-2">
											{t("nav.paper_library")}
										</p>

										<div className="space-y-1">
											{isPapersLoading ? (
												<div className="space-y-1.5 px-1">
													{[0, 1, 2].map((i) => (
														<div
															key={i}
															className="h-10 rounded-lg bg-slate-100 animate-pulse"
														/>
													))}
												</div>
											) : uploadedPapers.length === 0 ? (
												<div className="px-2 py-4 text-xs text-gray-500 italic">
													{t("nav.no_papers")}
												</div>
											) : (
												uploadedPapers.map((paper) => (
													<div
														key={paper.paper_id}
														className="relative group/card"
													>
														<button
															type="button"
															onClick={() => handlePaperSelect(paper)}
															className={`w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200 group relative ${
																currentPaperId === paper.paper_id
																	? "bg-orange-500 text-white shadow-lg shadow-orange-900/10"
																	: "text-slate-500 hover:bg-slate-50"
															}`}
														>
															<div className="flex items-start gap-3">
																<div
																	className={`mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full ${
																		currentPaperId === paper.paper_id
																			? "bg-orange-300"
																			: "bg-slate-200 group-hover:bg-slate-300"
																	}`}
																/>
																<div className="overflow-hidden pr-5">
																	<p
																		className={`text-sm font-medium leading-tight truncate ${
																			currentPaperId === paper.paper_id
																				? "text-white"
																				: "text-slate-700"
																		}`}
																	>
																		{paper.title || paper.filename}
																	</p>
																	<p className="text-[10px] opacity-50 mt-1 uppercase tracking-wider">
																		{new Date(
																			paper.created_at,
																		).toLocaleDateString()}
																	</p>
																</div>
															</div>
															{currentPaperId === paper.paper_id && (
																<div className="absolute left-0 top-2 bottom-2 w-1 bg-white rounded-r-full" />
															)}
														</button>
														{appEnv !== "prod" && (
															<button
																type="button"
																onClick={(e) => handleDeletePaper(e, paper)}
																className={`absolute right-2 top-1/2 -translate-y-1/2 z-10 opacity-100 sm:opacity-0 sm:group-hover/card:opacity-100 transition-opacity p-1.5 rounded ${
																	currentPaperId === paper.paper_id
																		? "text-white/70 hover:text-white hover:bg-white/20"
																		: "text-slate-400 hover:text-red-500 hover:bg-red-50"
																}`}
																title="削除"
															>
																<svg
																	xmlns="http://www.w3.org/2000/svg"
																	width="14"
																	height="14"
																	viewBox="0 0 24 24"
																	fill="none"
																	stroke="currentColor"
																	strokeWidth="2"
																	strokeLinecap="round"
																	strokeLinejoin="round"
																>
																	<path d="M3 6h18" />
																	<path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
																	<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
																</svg>
															</button>
														)}
													</div>
												))
											)}
										</div>

										<div className="mt-8 mb-4">
											<RequestForm />
										</div>
									</div>

									<div className="mt-auto pt-6 border-t border-slate-100 mb-4 px-2">
										{user ? (
											<div className="space-y-4">
												<div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200 backdrop-blur-sm">
													<div className="relative">
														{user.image ? (
															<img
																src={user.image}
																alt="User"
																className="w-10 h-10 rounded-full border-2 border-orange-500/30 shadow-inner"
															/>
														) : (
															<div className="w-10 h-10 rounded-full bg-gradient-to-tr from-orange-500 to-amber-400 flex items-center justify-center text-sm font-black shadow-lg shadow-orange-500/10 text-white">
																{user.name?.[0] || user.email?.[0] || "U"}
															</div>
														)}
														<div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-green-500 border-2 border-white rounded-full shadow-sm" />
													</div>
													<div className="overflow-hidden">
														<div className="flex items-center gap-1.5">
															<p className="text-sm font-bold text-slate-800 truncate">
																{user.name ||
																	user.email?.split("@")[0] ||
																	"User"}
															</p>
														</div>
														<p className="text-[10px] text-green-400 font-bold uppercase tracking-wider flex items-center gap-1">
															<span className="w-1 h-1 bg-green-400 rounded-full animate-pulse" />
															{t("nav.status_logged_in")}
														</p>
													</div>
												</div>
												<button
													type="button"
													onClick={logout}
													className="group w-full py-2.5 px-4 bg-slate-50 hover:bg-red-50 text-slate-500 hover:text-red-600 rounded-xl text-xs font-bold transition-all duration-300 border border-slate-200 hover:border-red-200 flex items-center justify-center gap-2"
												>
													<svg
														className="w-4 h-4 transition-transform group-hover:-translate-x-0.5"
														fill="none"
														stroke="currentColor"
														viewBox="0 0 24 24"
													>
														<path
															strokeLinecap="round"
															strokeLinejoin="round"
															strokeWidth="2.5"
															d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
														/>
													</svg>
													{t("nav.signout")}
												</button>
											</div>
										) : (
											<div className="space-y-4">
												<div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-dashed border-slate-200">
													<div className="w-10 h-10 rounded-full bg-gray-700/50 flex items-center justify-center text-xs font-bold text-gray-500">
														<svg
															className="w-5 h-5"
															fill="none"
															stroke="currentColor"
															viewBox="0 0 24 24"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth="2"
																d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
															/>
														</svg>
													</div>
													<div className="overflow-hidden">
														<p className="text-sm font-bold text-gray-400 truncate">
															{t("nav.guest_user")}
														</p>
														<p className="text-[10px] text-gray-500 font-medium truncate uppercase tracking-tight">
															{t("nav.limited_access")}
														</p>
													</div>
												</div>
												<button
													type="button"
													onClick={() => setShowLoginModal(true)}
													className="w-full py-3 px-4 bg-orange-500 hover:bg-orange-400 text-white rounded-xl text-xs font-black transition-all duration-300 shadow-lg shadow-orange-500/10 active:scale-[0.98] flex items-center justify-center gap-2"
												>
													<svg
														className="w-4 h-4"
														fill="none"
														stroke="currentColor"
														viewBox="0 0 24 24"
													>
														<path
															strokeLinecap="round"
															strokeLinejoin="round"
															strokeWidth="2.5"
															d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
														/>
													</svg>
													{t("nav.signin_signup")}
												</button>
											</div>
										)}
									</div>

									<div className="mt-8 px-2">
										<div className="relative group">
											<div className="absolute -inset-0.5 bg-gradient-to-r from-orange-400 to-amber-400 rounded-2xl blur opacity-10 group-hover:opacity-20 transition duration-300"></div>
											<div className="relative bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all duration-300">
												<label
													htmlFor="pdf-upload-input"
													className="flex flex-col items-center cursor-pointer group/label"
												>
													<div className="w-10 h-10 rounded-full bg-orange-50 flex items-center justify-center mb-3 group-hover/label:scale-110 group-hover/label:bg-orange-100 transition-all duration-300">
														<svg
															className="w-5 h-5 text-orange-500"
															fill="none"
															stroke="currentColor"
															viewBox="0 0 24 24"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth="2.5"
																d="M12 4v16m8-8H4"
															/>
														</svg>
													</div>
													<div className="text-center">
														<span className="block text-sm font-black text-slate-800 tracking-tight mb-1">
															{t("nav.upload_pdf")}
														</span>
														<span className="block text-[10px] text-amber-500 font-bold uppercase tracking-wider mb-2">
															{t("nav.only_english_supported")}
														</span>
													</div>
													<div className="w-full py-2 px-4 bg-slate-900 text-white rounded-xl text-[10px] font-black uppercase tracking-[0.1em] flex items-center justify-center gap-2 group-hover/label:bg-orange-600 transition-colors duration-300 shadow-lg shadow-slate-900/10">
														<svg
															className="w-3.5 h-3.5"
															fill="none"
															stroke="currentColor"
															viewBox="0 0 24 24"
														>
															<path
																strokeLinecap="round"
																strokeLinejoin="round"
																strokeWidth="3"
																d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
															/>
														</svg>
														{t("nav.select_file", "Select PDF")}
													</div>
													<input
														id="pdf-upload-input"
														type="file"
														accept="application/pdf"
														onChange={handleFileChange}
														className="hidden"
													/>
												</label>
											</div>
										</div>
									</div>
								</div>
							</div>

							{/* Main Content Area */}
							<div className="flex-1 min-w-0 flex flex-col h-full relative transition-all duration-300">
								<header className="h-14 sm:h-12 bg-white border-b border-slate-200 flex items-center px-2 sm:px-4 header-container overflow-hidden">
									{!isLeftSidebarOpen && (
										<button
											type="button"
											onClick={() => setIsLeftSidebarOpen(true)}
											className="mr-2 sm:mr-4 px-2 sm:px-4 py-2 rounded-xl bg-orange-50/50 text-orange-600 border border-orange-200 hover:bg-orange-500 hover:text-white transition-all duration-300 flex items-center justify-center gap-1 sm:gap-2 shadow-sm hover:shadow-orange-200 group/nav"
											title={t("nav.open_menu")}
										>
											<svg
												className="w-4 h-4 transition-transform group-hover/nav:translate-x-0.5"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth="3"
													d="M13 5l7 7-7 7M5 5l7 7-7 7"
												/>
											</svg>
											<span className="header-shrink-text font-black tracking-widest uppercase">
												{t("nav.menu_label")}
											</span>
										</button>
									)}
									{import.meta.env.MODE === "development" && (
										<button
											type="button"
											onClick={() => {
												throw new Error("Sentry Test Error: Break the world");
											}}
											className="mr-2 sm:mr-4 px-2 sm:px-3 py-2 rounded-md bg-red-500 text-white header-shrink-text font-bold hover:bg-red-600 transition-all shadow-sm"
										>
											Break the world
										</button>
									)}
									{(uploadFile || currentPaperId) && (
										<>
											<div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
												<button
													type="button"
													onClick={() =>
														startModeTransition(() => setPdfMode("plaintext"))
													}
													className={`px-1.5 sm:px-3 py-1.5 rounded-lg header-shrink-text font-black uppercase tracking-wider transition-all duration-200 flex items-center gap-1 sm:gap-2 ${
														pdfMode === "plaintext"
															? "bg-white text-orange-600 shadow-sm"
															: "text-slate-400 hover:text-slate-600"
													} ${isModeTransitionPending ? "opacity-60" : ""}`}
												>
													<span className="text-xs">📝</span>
													{t("viewer.toolbar.text_mode")}
												</button>
												<button
													type="button"
													onClick={() =>
														startModeTransition(() => setPdfMode("text"))
													}
													className={`px-1.5 sm:px-3 py-1.5 rounded-lg header-shrink-text font-black uppercase tracking-wider transition-all duration-200 flex items-center gap-1 sm:gap-2 ${
														pdfMode === "text"
															? "bg-white text-orange-600 shadow-sm"
															: "text-slate-400 hover:text-slate-600"
													} ${isModeTransitionPending ? "opacity-60" : ""}`}
												>
													<span className="text-xs">📄</span>
													{t("viewer.toolbar.click_mode")}
												</button>
											</div>
											<div
												className="ml-3 flex items-center gap-2"
												title={`Sync: ${syncStatus}`}
											>
												<div
													className={`w-2 h-2 rounded-full ${
														syncStatus === "synced"
															? "bg-green-500"
															: syncStatus === "pending"
																? "bg-amber-500 animate-pulse"
																: "bg-red-500"
													}`}
												/>
											</div>
										</>
									)}
									<div className="flex-1 min-w-0" />
									{uploadFile && (
										<span className="header-shrink-text font-bold text-slate-400 uppercase tracking-wider mr-2 sm:mr-4 truncate max-w-[120px] sm:max-w-xs">
											{uploadFile.name}
										</span>
									)}
									{!isGuest && user && (
										<button
											type="button"
											onClick={() => navigate("/dashboard")}
											className="mr-2 sm:mr-3 flex items-center gap-1.5 px-2 sm:px-3 py-2 rounded-xl hover:bg-orange-50 transition-colors group/dash border border-transparent hover:border-orange-200"
											title="マイダッシュボード"
										>
											{user.image ? (
												<img
													src={user.image}
													alt={user.name ?? ""}
													className="w-6 h-6 rounded-lg object-cover"
												/>
											) : (
												<div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-orange-600 to-amber-500 flex items-center justify-center text-white text-[10px] font-bold">
													{(user.name ?? user.email ?? "U")
														.charAt(0)
														.toUpperCase()}
												</div>
											)}
											<span className="header-shrink-text text-xs font-semibold text-slate-500 group-hover/dash:text-orange-600 transition-colors hidden sm:block">
												Dashboard
											</span>
										</button>
									)}
									<button
										type="button"
										onClick={() => setIsRightSidebarOpen((prev) => !prev)}
										className={`ml-2 sm:ml-4 px-2 sm:px-4 py-2 rounded-xl transition-all duration-300 flex items-center justify-center gap-1 sm:gap-2 border shadow-sm group/assist
								${
									isRightSidebarOpen
										? "bg-slate-900 text-white border-slate-800 hover:bg-orange-500 hover:border-orange-400"
										: "bg-orange-50/50 text-orange-600 border-orange-200 hover:bg-orange-500 hover:text-white hover:shadow-orange-200"
								}`}
										title={
											isRightSidebarOpen
												? t("nav.close_right_panel", "Close panel")
												: t("nav.open_right_panel", "Open panel")
										}
									>
										<span className="header-shrink-text font-black tracking-widest uppercase">
											{t("nav.assistant_label")}
										</span>
										<svg
											className={`w-4 h-4 transition-transform ${isRightSidebarOpen ? "group-hover/assist:translate-x-0.5" : "group-hover/assist:-translate-x-0.5"}`}
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											{isRightSidebarOpen ? (
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth="3"
													d="M13 5l7 7-7 7M5 5l7 7-7 7"
												/>
											) : (
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth="3"
													d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
												/>
											)}
										</svg>
									</button>
								</header>

								<div className="flex-1 flex overflow-hidden">
									{/* PDF Viewer Area */}
									<div className="flex-1 bg-slate-100 flex items-start justify-center relative overflow-hidden">
										{uploadFile || currentPaperId ? (
											<div
												ref={zoomContainerRef}
												onScroll={handleScroll}
												onWheel={handleZoomWheel}
												className={`w-full h-full ${zoom > 1 ? "overflow-auto" : "overflow-y-auto overflow-x-hidden"} custom-scrollbar`}
												style={{
													touchAction:
														zoom > 1 ? "pan-x pan-y" : "pan-y pinch-zoom",
												}}
											>
												{/* スペーサー: transform後の視覚サイズに合わせてスクロール領域を確保 */}
												<div
													style={{
														width: zoom > 1 ? `${zoom * 100}%` : "100%",
														minHeight: "100%",
													}}
												>
													{/* ズームtransformラッパー */}
													<div
														className="p-2 sm:p-4 md:p-8"
														style={
															zoom > 1
																? {
																		transform: `scale(${zoom})`,
																		transformOrigin: "top left",
																		width: `${(100 / zoom).toFixed(4)}%`,
																	}
																: undefined
														}
													>
														<PDFViewer
															sessionId={sessionId}
															uploadFile={uploadFile}
															paperId={currentPaperId}
															onWordClick={handleWordClick}
															onTextSelect={handleTextSelect}
															onAreaSelect={handleAreaSelect}
															jumpTarget={jumpTarget}
															onStatusChange={handleAnalysisStatusChange}
															onPaperLoaded={handlePaperLoaded}
															onAskAI={handleAskAI}
															onFigureSelect={handleFigureSelect}
															searchTerm={searchTerm}
															onSearchMatchesUpdate={handleSearchMatchesUpdate}
															currentSearchMatch={currentSearchMatch}
															evidence={activeEvidence}
															appEnv={appEnv}
															maxPdfSize={maxPdfSize}
															mode={pdfMode}
														/>
													</div>
												</div>
												{/* ズームコントロール */}
												{(uploadFile || currentPaperId) && (
													<div className="sticky bottom-4 left-4 z-50 inline-flex items-center gap-0.5 bg-slate-800/80 text-white text-xs font-semibold rounded-full shadow-lg backdrop-blur-sm">
														<button
															type="button"
															onClick={zoomOut}
															disabled={zoom <= 1}
															className="px-2.5 py-1.5 hover:bg-slate-700/90 rounded-l-full transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
															aria-label="ズームアウト"
														>
															−
														</button>
														<button
															type="button"
															onClick={resetZoom}
															className="px-2 py-1.5 hover:bg-slate-700/90 transition-colors min-w-[3.5rem] text-center"
															aria-label="ズームリセット"
														>
															{Math.round(zoom * 100)}%
														</button>
														<button
															type="button"
															onClick={zoomIn}
															disabled={zoom >= 4}
															className="px-2.5 py-1.5 hover:bg-slate-700/90 rounded-r-full transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
															aria-label="ズームイン"
														>
															＋
														</button>
													</div>
												)}
											</div>
										) : (
											<div className="w-full h-full flex items-center justify-center p-4">
												<UploadScreen onFileSelect={handleDirectFileSelect} />
											</div>
										)}
									</div>

									{/* Resizer Handle */}
									<hr
										aria-orientation="vertical"
										aria-valuenow={sidebarWidth}
										aria-valuemin={150}
										aria-valuemax={500}
										tabIndex={0}
										className={`hidden md:block w-1.5 h-full cursor-col-resize hover:bg-slate-500/10 transition-colors z-30 shrink-0 border-none m-0 p-0 ${isResizing ? "bg-slate-500/20" : "bg-transparent"}`}
										onMouseDown={(e) => {
											e.preventDefault();
											setIsResizing(true);
										}}
										onKeyDown={(e) => {
											if (e.key === "ArrowLeft") {
												setSidebarWidth((w: number) =>
													clampWidth(
														w - 10,
														window.innerWidth,
														isLeftSidebarOpen,
													),
												);
											} else if (e.key === "ArrowRight") {
												setSidebarWidth((w: number) =>
													clampWidth(
														w + 10,
														window.innerWidth,
														isLeftSidebarOpen,
													),
												);
											}
										}}
									/>

									{/* Mobile Backdrop for Right Sidebar */}
									{isRightSidebarOpen && (
										<button
											type="button"
											className="fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity w-full h-full border-none p-0 cursor-default"
											onClick={() => setIsRightSidebarOpen(false)}
											aria-label="Close right sidebar"
										/>
									)}

									{/* Right Sidebar */}
									<div
										style={{
											width: isMobile
												? "90vw"
												: isRightSidebarOpen
													? sidebarWidth
													: 0,
										}}
										className={`fixed top-0 right-0 md:relative md:top-auto md:right-auto h-screen h-dvh md:h-full shadow-xl z-50 md:z-20 bg-white overflow-hidden shrink-0 transition-all duration-300 ${
											isRightSidebarOpen
												? "translate-x-0"
												: "translate-x-full md:translate-x-0"
										}`}
									>
										<Sidebar
											onClose={() => setIsRightSidebarOpen(false)}
											sessionId={sessionId}
											activeTab={activeTab}
											onTabChange={setActiveTab}
											dictSubTab={dictSubTab}
											onDictSubTabChange={setDictSubTab}
											selectedWord={
												dictSubTab === "translation"
													? translationWord
													: dictSubTab === "explanation"
														? explanationWord
														: selectedWord
											}
											context={
												dictSubTab === "translation"
													? translationContext
													: dictSubTab === "explanation"
														? explanationContext
														: selectedContext
											}
											coordinates={
												dictSubTab === "translation"
													? translationCoordinates
													: dictSubTab === "explanation"
														? explanationCoordinates
														: selectedCoordinates
											}
											conf={
												dictSubTab === "translation"
													? translationConf
													: undefined
											}
											selectedImage={selectedImage}
											onJump={handleJumpToLocation}
											isAnalyzing={isAnalyzing}
											paperId={currentPaperId}
											selectedFigure={selectedFigure}
											pendingFigureId={pendingFigureId}
											onPendingFigureConsumed={() => setPendingFigureId(null)}
											pendingChatPrompt={pendingChatPrompt}
											onPendingChatConsumed={() => setPendingChatPrompt(null)}
											onEvidenceClick={(g: any) => {
												setActiveEvidence(g);
												// Optionally switch to PDF view if in plaintext mode?
												// For now just set evidence.
											}}
										/>
									</div>
								</div>
							</div>

							{/* Login Modal */}
							{showLoginModal && (
								<button
									type="button"
									className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 transition-opacity duration-300 w-full h-full border-none p-0 cursor-default"
									onClick={() => setShowLoginModal(false)}
									onKeyDown={(e) => {
										if (e.key === "Enter" || e.key === " ") {
											setShowLoginModal(false);
										}
									}}
									aria-label="Close login modal"
								>
									<div
										className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden animate-in zoom-in-95 duration-200"
										onClick={(e) => e.stopPropagation()}
										onKeyDown={(e) => e.stopPropagation()}
										role="dialog"
										aria-modal="true"
									>
										<Login />
										<button
											type="button"
											onClick={() => setShowLoginModal(false)}
											className="absolute top-4 right-4 p-2 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-full transition-all duration-200 z-[60]"
											aria-label="Close"
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
									</div>
								</button>
							)}

							{/* Search Bar */}
							<SearchBar
								isOpen={isSearchOpen}
								onClose={handleCloseSearch}
								searchTerm={searchTerm}
								onSearchTermChange={setSearchTerm}
								matches={searchMatches}
								currentMatchIndex={currentMatchIndex}
								onNextMatch={handleNextMatch}
								onPrevMatch={handlePrevMatch}
							/>
							<GlobalLoading />
							{!isHealthy && (
								<ServiceOutage
									isMaintenance={isMaintenance}
									message={healthMessage}
								/>
							)}
						</div>
					</ErrorBoundary>
				}
			/>
		</Routes>
	);
}

export default App;

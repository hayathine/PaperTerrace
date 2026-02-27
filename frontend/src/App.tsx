import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import Login from "./components/Auth/Login";
import ErrorBoundary from "./components/Error/ErrorBoundary";
import PDFViewer from "./components/PDF/PDFViewer";
import SearchBar from "./components/Search/SearchBar";
import Sidebar from "./components/Sidebar/Sidebar";
import GlobalLoading from "./components/UI/GlobalLoading";
import UploadScreen from "./components/Upload/UploadScreen";
import { useAuth } from "./contexts/AuthContext";
import { useLoading } from "./contexts/LoadingContext";
import { syncTrajectory } from "./lib/recommendation";

function App() {
	const { user, logout } = useAuth();
	const { t } = useTranslation();
	const { startLoading, stopLoading } = useLoading();
	const [uploadFile, setUploadFile] = useState<File | null>(null);

	const [currentPaperId, setCurrentPaperId] = useState<string | null>(null);
	const [isAnalyzing, setIsAnalyzing] = useState(false);

	// Sync isAnalyzing with GlobalLoading
	useEffect(() => {
		if (isAnalyzing) {
			startLoading();
		} else {
			stopLoading();
		}
	}, [isAnalyzing, startLoading, stopLoading]);

	// Sidebar State
	const [sessionId] = useState(() => {
		const saved = localStorage.getItem("paper_terrace_session");
		if (saved) return saved;
		const newId = `session-${Math.random().toString(36).substring(2, 11)}`;
		localStorage.setItem("paper_terrace_session", newId);
		return newId;
	});
	const [activeTab, setActiveTab] = useState("chat");
	const [selectedWord, setSelectedWord] = useState<string | undefined>(
		undefined,
	);
	const [selectedContext, setSelectedContext] = useState<string | undefined>(
		undefined,
	);
	const [selectedCoordinates, setSelectedCoordinates] = useState<
		{ page: number; x: number; y: number } | undefined
	>(undefined);
	const [selectedConf, setSelectedConf] = useState<number | undefined>(
		undefined,
	);
	const [selectedImage, setSelectedImage] = useState<string | undefined>(
		undefined,
	);
	const [jumpTarget, setJumpTarget] = useState<{
		page: number;
		x: number;
		y: number;
		term?: string;
	} | null>(null);
	const [showLoginModal, setShowLoginModal] = useState(false);

	const [pendingFigureId, setPendingFigureId] = useState<string | null>(null);
	const [pendingChatPrompt, setPendingChatPrompt] = useState<string | null>(
		null,
	);
	const [sidebarWidth, setSidebarWidth] = useState(384);
	const [isResizing, setIsResizing] = useState(false);
	const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true);
	const [activeEvidence, setActiveEvidence] = useState<any>(null);
	const [stackedPapers, setStackedPapers] = useState<
		{ url: string; title?: string; addedAt: number }[]
	>(() => {
		try {
			const saved = localStorage.getItem("paper_terrace_stack");
			if (!saved) return [];
			const parsed = JSON.parse(saved);
			return Array.isArray(parsed) ? parsed : [];
		} catch (e) {
			console.error("Failed to parse stacked papers:", e);
			return [];
		}
	});
	const [uploadedPapers, setUploadedPapers] = useState<any[]>([]);

	const prevPaperIdRef = useRef<string | null>(null);

	// Developer settings
	const SHOW_DEV_TOOLS = true;

	useEffect(() => {
		localStorage.setItem("paper_terrace_stack", JSON.stringify(stackedPapers));
	}, [stackedPapers]);

	useEffect(() => {
		const fetchPapers = async () => {
			try {
				const headers: Record<string, string> = {};
				if (user) {
					const idToken = await user.getIdToken();
					headers.Authorization = `Bearer ${idToken}`;
				}

				const res = await fetch(`${API_URL}/api/papers`, { headers });
				const data = await res.json();
				if (data && Array.isArray(data.papers)) {
					setUploadedPapers(data.papers);
				} else {
					setUploadedPapers([]);
				}
			} catch (err) {
				console.error("Failed to fetch papers:", err);
				setUploadedPapers([]);
			}
		};

		fetchPapers();
	}, [user]);

	const { loginAsGuest: handleLoginAsGuest } = useAuth();

	// Context Cache Lifecycle Management
	useEffect(() => {
		const deleteCache = (paperId: string) => {
			const formData = new FormData();
			formData.append("session_id", sessionId);
			formData.append("paper_id", paperId);

			if (navigator.sendBeacon) {
				navigator.sendBeacon(`${API_URL}/api/chat/cache/delete`, formData);
			} else {
				fetch(`${API_URL}/api/chat/cache/delete`, {
					method: "POST",
					body: formData,
					keepalive: true,
				}).catch((e) => console.error("Failed to delete cache:", e));
			}
		};

		if (prevPaperIdRef.current && prevPaperIdRef.current !== currentPaperId) {
			deleteCache(prevPaperIdRef.current);
		}
		prevPaperIdRef.current = currentPaperId;
	}, [currentPaperId, sessionId]);

	useEffect(() => {
		const handleBeforeUnload = () => {
			if (currentPaperId) {
				const formData = new FormData();
				formData.append("session_id", sessionId);
				formData.append("paper_id", currentPaperId);
				navigator.sendBeacon(`${API_URL}/api/chat/cache/delete`, formData);
			}
		};

		window.addEventListener("beforeunload", handleBeforeUnload);
		return () => window.removeEventListener("beforeunload", handleBeforeUnload);
	}, [currentPaperId, sessionId]);

	const [isMobile, setIsMobile] = useState(false);
	const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);

	useEffect(() => {
		const checkMobile = () => setIsMobile(window.innerWidth < 768);
		checkMobile();
		window.addEventListener("resize", checkMobile);
		return () => window.removeEventListener("resize", checkMobile);
	}, []);

	useEffect(() => {
		const handleMouseMove = (e: MouseEvent) => {
			if (!isResizing) return;
			// Calculate new width from right side
			const newWidth = window.innerWidth - e.clientX;
			// Constrain width between 200px and half the screen
			if (newWidth > 200 && newWidth < window.innerWidth * 0.7) {
				setSidebarWidth(newWidth);
			}
		};

		const handleMouseUp = () => {
			setIsResizing(false);
			document.body.style.cursor = "default";
			document.body.style.userSelect = "auto";
		};

		if (isResizing) {
			window.addEventListener("mousemove", handleMouseMove);
			window.addEventListener("mouseup", handleMouseUp);
			document.body.style.cursor = "col-resize";
			document.body.style.userSelect = "none";
		}

		return () => {
			window.removeEventListener("mousemove", handleMouseMove);
			window.removeEventListener("mouseup", handleMouseUp);
		};
	}, [isResizing]);

	const handlePaperLoaded = (paperId: string | null) => {
		if (paperId) {
			setCurrentPaperId(paperId);
			setUploadFile(null); // Clear the raw file after it's processed
		}
		// Refresh paper list if a new paper was loaded
		if (
			paperId &&
			Array.isArray(uploadedPapers) &&
			!uploadedPapers.some((p) => p?.paper_id === paperId)
		) {
			fetch(`${API_URL}/api/papers`)
				.then((res) => res.json())
				.then((data) => {
					if (data && Array.isArray(data.papers)) {
						setUploadedPapers(data.papers);
					} else {
						setUploadedPapers([]);
					}
				})
				.catch((err) => {
					console.error("Failed to refresh papers:", err);
				});
		}
	};

	const handlePaperSelect = (paper: any) => {
		setUploadFile(null);
		setCurrentPaperId(paper.paper_id);
	};

	const handleDirectFileSelect = (file: File) => {
		setUploadFile(file);
		setCurrentPaperId(null);
		// Reset all paper-specific states
		setSelectedWord(undefined);
		setSelectedContext(undefined);
		setSelectedCoordinates(undefined);
		setSelectedImage(undefined);
		setPendingChatPrompt(null);
		setPendingFigureId(null);
		setActiveTab("chat");
	};

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		if (e.target.files?.[0]) {
			handleDirectFileSelect(e.target.files[0]);
		}
	};

	const isLink = (text: string) => {
		const clean = text.trim();
		return (
			clean.match(/^(https?:\/\/|\/\/)/i) ||
			clean.startsWith("www.") ||
			clean.includes("doi.org/") ||
			clean.match(
				/[a-zA-Z0-9.-]+\.(com|org|net|io|edu|gov|io|github\.io)\//i,
			) ||
			clean.match(/^10\.\d{4,9}\/[-._;()/:A-Z0-9]+$/i)
		); // DOI pattern
	};

	const handleWordClick = (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
		conf?: number,
	) => {
		if (isLink(word)) {
			handleStackPaper(word);
			return;
		}

		// Fire telemetry for translation
		if (currentPaperId) {
			syncTrajectory({
				session_id: sessionId,
				paper_id: currentPaperId,
				word_clicks: [
					{
						word,
						context: context || "",
						section: "Unknown", // Can be inferred if PDF structure allows, or left as Unknown
						timestamp: Date.now() / 1000,
					},
				],
			});
		}

		setSelectedWord(word);
		setSelectedContext(context);
		setSelectedCoordinates(coords);
		setSelectedConf(conf);
		setActiveTab("dict");
		setIsRightSidebarOpen(true);
	};

	const handleTextSelect = (
		text: string,
		coords: { page: number; x: number; y: number },
	) => {
		if (isLink(text)) {
			handleStackPaper(text);
			return;
		}

		// When text is selected, we want to maybe open notes?
		// Let's set selected context as the text
		setSelectedWord(undefined);
		setSelectedContext(text);
		setSelectedImage(undefined); // Clear image
		setSelectedCoordinates(coords);
		setActiveTab("notes"); // Switch to notes for saving selection
		setIsRightSidebarOpen(true);
	};

	const handleAreaSelect = (
		imageUrl: string,
		coords: { page: number; x: number; y: number },
	) => {
		setSelectedWord(undefined);
		setSelectedContext(undefined);
		setSelectedImage(imageUrl);
		setSelectedCoordinates(coords);
		setActiveTab("notes");
		setIsRightSidebarOpen(true);
	};

	const handleJumpToLocation = (
		page: number,
		x: number,
		y: number,
		term?: string,
	) => {
		setJumpTarget({ page, x, y, term });
		// Clear jump target after a short delay so highlight doesn't stay forever if desired,
		// but for now let's keep it until next jump.
	};

	const handleAnalysisStatusChange = useCallback((status: string) => {
		// Show analyzing state during upload and processing
		setIsAnalyzing(status === "uploading" || status === "processing");
	}, []);

	const handleAskAI = (prompt: string) => {
		setPendingChatPrompt(prompt);
		setActiveTab("chat");
		setIsRightSidebarOpen(true);
	};

	const handleStackPaper = (url: string, title?: string) => {
		// Heal URL if it looks like one (remove internal spaces/newlines from OCR/layout split)
		let cleanedUrl = url.trim().replace(/\s+/g, "");

		// Handle raw DOI
		if (cleanedUrl.match(/^10\.\d{4,9}\//) && !cleanedUrl.startsWith("http")) {
			cleanedUrl = `https://doi.org/${cleanedUrl}`;
		}

		setStackedPapers((prev) => {
			if (prev.some((p) => p.url === cleanedUrl)) return prev;
			return [...prev, { url: cleanedUrl, title, addedAt: Date.now() }];
		});
		setActiveTab("stack");
		setIsRightSidebarOpen(true);
	};

	const handleRemoveFromStack = (url: string) => {
		setStackedPapers((prev) => prev.filter((p) => p.url !== url));
	};

	// Ctrl+F イベントをインターセプトしてカスタム検索を開く
	const [isSearchOpen, setIsSearchOpen] = useState(false);
	const [searchTerm, setSearchTerm] = useState("");
	const [searchMatches, setSearchMatches] = useState<
		Array<{ page: number; wordIndex: number }>
	>([]);
	const [currentMatchIndex, setCurrentMatchIndex] = useState(0);

	// 現在の検索マッチ
	const currentSearchMatch =
		searchMatches.length > 0 && currentMatchIndex < searchMatches.length
			? searchMatches[currentMatchIndex]
			: null;

	// 検索マッチのナビゲーション
	const handleNextMatch = useCallback(() => {
		if (searchMatches.length === 0) return;
		setCurrentMatchIndex((prev) => (prev + 1) % searchMatches.length);
	}, [searchMatches.length]);

	const handlePrevMatch = useCallback(() => {
		if (searchMatches.length === 0) return;
		setCurrentMatchIndex(
			(prev) => (prev - 1 + searchMatches.length) % searchMatches.length,
		);
	}, [searchMatches.length]);

	// 検索を閉じる
	const handleCloseSearch = useCallback(() => {
		setIsSearchOpen(false);
		setSearchTerm("");
		setSearchMatches([]);
		setCurrentMatchIndex(0);
	}, []);

	// 検索マッチの更新
	const handleSearchMatchesUpdate = useCallback(
		(matches: Array<{ page: number; wordIndex: number }>) => {
			setSearchMatches(matches);
			setCurrentMatchIndex(0);
		},
		[],
	);

	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			// Ctrl+F または Cmd+F (Mac)
			if ((e.ctrlKey || e.metaKey) && e.key === "f") {
				// PDFが表示されている場合のみカスタム検索を有効化
				if (uploadFile || currentPaperId) {
					e.preventDefault();
					setIsSearchOpen(true);
				}
			}
			// Escで検索を閉じる
			if (e.key === "Escape" && isSearchOpen) {
				handleCloseSearch();
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [uploadFile, currentPaperId, isSearchOpen, handleCloseSearch]);

	return (
		<ErrorBoundary>
			<div className="flex h-screen w-full bg-gray-100 overflow-hidden">
				{/* Mobile Backdrop for Left Sidebar */}
				{isLeftSidebarOpen && (
					<button
						type="button"
						className="fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity w-full h-full border-none p-0 cursor-default"
						onClick={() => setIsLeftSidebarOpen(false)}
						aria-label="Close left sidebar"
					/>
				)}

				{/* Left Sidebar */}
				<div
					className={`bg-gray-900 text-white transition-all duration-300 ease-in-out flex flex-col shrink-0 absolute md:relative z-50 h-full ${
						isLeftSidebarOpen
							? "w-72 md:w-64 translate-x-0"
							: "-translate-x-full md:translate-x-0 w-72 md:w-0 overflow-hidden"
					}`}
				>
					<div className="w-64 p-4 flex flex-col h-full">
						<div className="flex items-center gap-3 mb-8">
							<button
								type="button"
								onClick={() => setIsLeftSidebarOpen(false)}
								className="p-1.5 rounded-md hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
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
										strokeWidth="2.5"
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
								{uploadedPapers.length === 0 ? (
									<div className="px-2 py-4 text-xs text-gray-500 italic">
										{t("nav.no_papers")}
									</div>
								) : (
									uploadedPapers.map((paper) => (
										<button
											type="button"
											key={paper.paper_id}
											onClick={() => handlePaperSelect(paper)}
											className={`w-full text-left px-3 py-2.5 rounded-lg transition-all duration-200 group relative ${
												currentPaperId === paper.paper_id
													? "bg-indigo-600 text-white shadow-lg shadow-indigo-900/20"
													: "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
											}`}
										>
											<div className="flex items-start gap-3">
												<div
													className={`mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full ${
														currentPaperId === paper.paper_id
															? "bg-indigo-300"
															: "bg-gray-700 group-hover:bg-gray-500"
													}`}
												/>
												<div className="overflow-hidden">
													<p
														className={`text-sm font-medium leading-tight truncate ${
															currentPaperId === paper.paper_id
																? "text-white"
																: "text-gray-300"
														}`}
													>
														{paper.title || paper.filename}
													</p>
													<p className="text-[10px] opacity-50 mt-1 uppercase tracking-wider">
														{new Date(paper.created_at).toLocaleDateString()}
													</p>
												</div>
											</div>
											{currentPaperId === paper.paper_id && (
												<div className="absolute left-0 top-2 bottom-2 w-1 bg-white rounded-r-full" />
											)}
										</button>
									))
								)}
							</div>
						</div>

						<div className="mt-auto pt-6 border-t border-gray-800/50 mb-4 px-2">
							{user ? (
								<div className="space-y-4">
									<div className="flex items-center gap-3 p-3 bg-gray-800/40 rounded-xl border border-gray-700/30 backdrop-blur-sm">
										<div className="relative">
											{user.photoURL ? (
												<img
													src={user.photoURL}
													alt="User"
													className="w-10 h-10 rounded-full border-2 border-indigo-500/30 shadow-inner"
												/>
											) : (
												<div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-600 to-purple-500 flex items-center justify-center text-sm font-black shadow-lg shadow-indigo-500/20">
													{user.displayName?.[0] || user.email?.[0] || "U"}
												</div>
											)}
											<div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-green-500 border-2 border-gray-900 rounded-full shadow-sm" />
										</div>
										<div className="overflow-hidden">
											<div className="flex items-center gap-1.5">
												<p className="text-sm font-bold text-gray-100 truncate">
													{user.displayName ||
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
										className="group w-full py-2.5 px-4 bg-gray-800 hover:bg-red-900/20 text-gray-400 hover:text-red-400 rounded-xl text-xs font-bold transition-all duration-300 border border-gray-700 hover:border-red-900/30 flex items-center justify-center gap-2"
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
									<div className="flex items-center gap-3 p-3 bg-gray-800/20 rounded-xl border border-dashed border-gray-700/50">
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
										className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-black transition-all duration-300 shadow-lg shadow-indigo-600/20 active:scale-[0.98] flex items-center justify-center gap-2"
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

						<div className="mt-4">
							<label
								htmlFor="pdf-upload-input"
								className="block text-xs font-bold mb-2 text-gray-400"
							>
								{t("nav.upload_pdf")}
							</label>
							<p className="text-[10px] text-amber-400/80 mb-2 leading-tight">
								{t("nav.only_english_supported")}
							</p>
							<input
								id="pdf-upload-input"
								type="file"
								accept="application/pdf"
								onChange={handleFileChange}
								className="block w-full text-sm text-gray-400
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-gray-700 file:text-white
                  hover:file:bg-gray-600
                  cursor-pointer
                "
							/>

							{SHOW_DEV_TOOLS && (
								<div className="mt-4 pt-4 border-t border-gray-700">
									<button
										type="button"
										onClick={() => {
											fetch(`${API_URL}/test.pdf`)
												.then((res) => res.blob())
												.then((blob) => {
													const file = new File([blob], "test.pdf", {
														type: "application/pdf",
													});
													setUploadFile(file);
													setCurrentPaperId(null);
												})
												.catch((e) =>
													console.error("Failed to load test PDF:", e),
												);
										}}
										id="dev-load-pdf-btn"
										className="w-full py-1 px-3 bg-indigo-900/50 hover:bg-indigo-900 text-indigo-200 text-xs rounded border border-indigo-800 transition-colors"
									>
										{t("viewer.loading_test")}
									</button>
								</div>
							)}
						</div>
					</div>
				</div>

				{/* Main Content Area */}
				<div className="flex-1 flex flex-col h-full relative transition-all duration-300">
					<header className="h-12 bg-white border-b border-slate-200 flex items-center px-4">
						{!isLeftSidebarOpen && (
							<button
								type="button"
								onClick={() => setIsLeftSidebarOpen(true)}
								className="mr-4 p-2 rounded-md bg-white text-slate-500 border border-slate-200 hover:bg-slate-50 hover:text-indigo-600 hover:border-indigo-200 transition-all duration-200 flex items-center justify-center shadow-sm"
								title={t("nav.open_menu")}
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
										d="M4 6h16M4 12h16M4 18h16"
									/>
								</svg>
							</button>
						)}
						<span className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
							{t("nav.reading_mode")}
						</span>
						<div className="flex-1" />
						{uploadFile && (
							<span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-4 truncate max-w-[150px] sm:max-w-xs">
								{uploadFile.name}
							</span>
						)}
						<button
							type="button"
							onClick={() => setIsRightSidebarOpen(true)}
							className="md:hidden p-2 rounded-md bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors shadow-sm border border-indigo-100"
							title={t("nav.open_right_panel")}
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
									strokeWidth="2"
									d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
								/>
							</svg>
						</button>
					</header>

					<div className="flex-1 flex overflow-hidden">
						{/* PDF Viewer Area */}
						<div className="flex-1 bg-slate-100 flex items-start justify-center relative overflow-hidden">
							{uploadFile || currentPaperId ? (
								<div className="w-full h-full p-4 md:p-8 overflow-y-auto custom-scrollbar">
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
										searchTerm={searchTerm}
										onSearchMatchesUpdate={handleSearchMatchesUpdate}
										currentSearchMatch={currentSearchMatch}
										evidence={activeEvidence}
									/>
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
							className={`hidden md:block w-1.5 h-full cursor-col-resize hover:bg-indigo-500/30 transition-colors z-30 shrink-0 border-none m-0 p-0 ${isResizing ? "bg-indigo-500/50" : "bg-transparent"}`}
							onMouseDown={(e) => {
								e.preventDefault();
								setIsResizing(true);
							}}
							onKeyDown={(e) => {
								if (e.key === "ArrowLeft") {
									setSidebarWidth((w: number) => Math.max(150, w - 10));
								} else if (e.key === "ArrowRight") {
									setSidebarWidth((w: number) => Math.min(500, w + 10));
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
							style={{ width: isMobile ? "85vw" : sidebarWidth }}
							className={`absolute md:relative right-0 h-full shadow-xl z-50 md:z-20 bg-white overflow-hidden shrink-0 transition-transform duration-300 ${
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
								selectedWord={selectedWord}
								context={selectedContext}
								coordinates={selectedCoordinates}
								conf={selectedConf}
								selectedImage={selectedImage}
								onJump={handleJumpToLocation}
								isAnalyzing={isAnalyzing}
								paperId={currentPaperId}
								pendingFigureId={pendingFigureId}
								onPendingFigureConsumed={() => setPendingFigureId(null)}
								pendingChatPrompt={pendingChatPrompt}
								onPendingChatConsumed={() => setPendingChatPrompt(null)}
								stackedPapers={stackedPapers}
								onStackPaper={handleStackPaper}
								onRemoveFromStack={handleRemoveFromStack}
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
							<Login
								onGuestAccess={() => {
									handleLoginAsGuest();
									setShowLoginModal(false);
								}}
							/>
							<button
								type="button"
								onClick={() => setShowLoginModal(false)}
								className="absolute top-4 right-4 p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-full transition-all duration-200 z-[60]"
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
			</div>
		</ErrorBoundary>
	);
}

export default App;

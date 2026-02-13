import React, { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "./components/Sidebar/Sidebar";
import PDFViewer from "./components/PDF/PDFViewer";
import { useAuth } from "./contexts/AuthContext";
import Login from "./components/Auth/Login";
import ErrorBoundary from "./components/Error/ErrorBoundary";
import UploadScreen from "./components/Upload/UploadScreen";
import SearchBar from "./components/Search/SearchBar";
import GlobalLoading from "./components/UI/GlobalLoading";
import { useLoading } from "./contexts/LoadingContext";

function App() {
  const { user, logout } = useAuth();
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
    if (user) {
      setShowLoginModal(false);

      fetch("/api/papers")
        .then((res) => res.json())
        .then((data) => {
          if (data && Array.isArray(data.papers)) {
            setUploadedPapers(data.papers);
          } else {
            setUploadedPapers([]);
          }
        })
        .catch((err) => {
          console.error("Failed to fetch papers:", err);
          setUploadedPapers([]);
        });
    }
  }, [user]);

  // Context Cache Lifecycle Management
  useEffect(() => {
    const deleteCache = (paperId: string) => {
      const formData = new FormData();
      formData.append("session_id", sessionId);
      formData.append("paper_id", paperId);

      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/chat/cache/delete", formData);
      } else {
        fetch("/api/chat/cache/delete", {
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
        navigator.sendBeacon("/api/chat/cache/delete", formData);
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [currentPaperId, sessionId]);

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
      fetch("/api/papers")
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
    if (e.target.files && e.target.files[0]) {
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
  ) => {
    if (isLink(word)) {
      handleStackPaper(word);
      return;
    }

    setSelectedWord(word);
    setSelectedContext(context);
    setSelectedCoordinates(coords);
    setActiveTab("dict");
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
    // Only show loading during upload, not during processing
    setIsAnalyzing(status === "uploading");
  }, []);

  const handleAskAI = (prompt: string) => {
    setPendingChatPrompt(prompt);
    setActiveTab("chat");
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
        {/* Sidebar Placeholder */}
        <div
          className={`bg-gray-900 text-white transition-all duration-300 ease-in-out hidden md:flex flex-col shrink-0 ${isLeftSidebarOpen ? "w-64 opacity-100" : "w-0 opacity-0 overflow-hidden"}`}
        >
          <div className="w-64 p-4 flex flex-col h-full">
            <div className="flex items-center gap-3 mb-8">
              <button
                onClick={() => setIsLeftSidebarOpen(false)}
                className="p-1.5 rounded-md hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
                title="メニューを閉じる"
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
                Paper Library
              </p>

              <div className="space-y-1">
                {uploadedPapers.length === 0 ? (
                  <div className="px-2 py-4 text-xs text-gray-500 italic">
                    No papers uploaded yet
                  </div>
                ) : (
                  uploadedPapers.map((paper) => (
                    <button
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

            <div className="mt-auto mb-4">
              {user && (
                <div className="flex items-center gap-2 mb-4 p-2 bg-gray-800 rounded">
                  {user.photoURL ? (
                    <img
                      src={user.photoURL}
                      alt="User"
                      className="w-8 h-8 rounded-full"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold">
                      {user.displayName?.[0] || "U"}
                    </div>
                  )}
                  <div className="overflow-hidden">
                    <p className="text-sm font-medium truncate">
                      {user.displayName || "User"}
                    </p>
                    <p className="text-xs text-gray-400 truncate">
                      {user.email || ""}
                    </p>
                  </div>
                </div>
              )}
              {!user && (
                <div className="flex items-center gap-2 mb-4 p-2 bg-gray-800 rounded">
                  <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-xs font-bold">
                    G
                  </div>
                  <div className="overflow-hidden">
                    <p className="text-sm font-medium truncate">Guest User</p>
                    <p className="text-xs text-gray-400 truncate">
                      Limited Access
                    </p>
                  </div>
                </div>
              )}
              {user ? (
                <button
                  onClick={logout}
                  className="w-full py-2 px-4 bg-red-600 hover:bg-red-700 rounded text-sm transition-colors"
                >
                  Sign Out
                </button>
              ) : (
                <button
                  onClick={() => setShowLoginModal(true)}
                  className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 rounded text-sm transition-colors"
                >
                  Sign In / Sign Up
                </button>
              )}
            </div>

            <div className="mt-4">
              <label className="block text-xs font-bold mb-2 text-gray-400">
                UPLOAD PDF
              </label>
              <p className="text-[10px] text-amber-400/80 mb-2 leading-tight">
                *現在、英語の論文のみサポートしています。
                <br />
                (Only English papers are supported)
              </p>
              <input
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
                    onClick={() => {
                      fetch("/test.pdf")
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
                    [DEV] Load Test.pdf
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
                onClick={() => setIsLeftSidebarOpen(true)}
                className="mr-4 p-2 rounded-md bg-white text-slate-500 border border-slate-200 hover:bg-slate-50 hover:text-indigo-600 hover:border-indigo-200 transition-all duration-200 flex items-center justify-center shadow-sm"
                title="メニューを開く"
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
              Reading Mode
            </span>
            <div className="flex-1" />
            {uploadFile && (
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                {uploadFile.name}
              </span>
            )}
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
                  />
                </div>
              ) : (
                <div className="w-full h-full flex items-center justify-center p-4">
                  <UploadScreen onFileSelect={handleDirectFileSelect} />
                </div>
              )}
            </div>

            {/* Resizer Handle */}
            <div
              className={`w-1.5 h-full cursor-col-resize hover:bg-indigo-500/30 transition-colors z-30 shrink-0 ${isResizing ? "bg-indigo-500/50" : "bg-transparent"}`}
              onMouseDown={(e) => {
                e.preventDefault();
                setIsResizing(true);
              }}
            >
              <div className="w-[1px] h-full bg-gray-200 mx-auto" />
            </div>

            {/* Right Sidebar */}
            <div
              style={{ width: sidebarWidth }}
              className="h-full shadow-xl z-20 bg-white overflow-hidden shrink-0"
            >
              <Sidebar
                sessionId={sessionId}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                selectedWord={selectedWord}
                context={selectedContext}
                coordinates={selectedCoordinates}
                selectedImage={selectedImage}
                onJump={handleJumpToLocation}
                isAnalyzing={isAnalyzing}
                paperId={currentPaperId}
                pendingFigureId={pendingFigureId}
                onPendingFigureConsumed={() => setPendingFigureId(null)}
                pendingChatPrompt={pendingChatPrompt}
                onAskAI={handleAskAI}
                onPendingChatConsumed={() => setPendingChatPrompt(null)}
                stackedPapers={stackedPapers}
                onStackPaper={handleStackPaper}
                onRemoveFromStack={handleRemoveFromStack}
              />
            </div>
          </div>
        </div>

        {/* Login Modal */}
        {showLoginModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
              <button
                onClick={() => setShowLoginModal(false)}
                className="absolute top-2 right-2 text-gray-400 hover:text-gray-600"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
              <Login onGuestAccess={() => setShowLoginModal(false)} />
            </div>
          </div>
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

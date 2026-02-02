import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import Sidebar from "./components/Sidebar/Sidebar";
import PDFViewer from "./components/PDF/PDFViewer";
import { useAuth } from "./contexts/AuthContext";
import Login from "./components/Auth/Login";
import PaperList from "./components/Library/PaperList";
import { PageData } from "./components/PDF/types";
import UploadZone from "./components/PDF/UploadZone";

function App() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const [config, setConfig] = useState<any>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

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
  const [evidenceHighlight, setEvidenceHighlight] = useState<{
    page: number;
    text: string;
    box_2d?: number[];
  } | null>(null);
  const [initialChatMessage, setInitialChatMessage] = useState<string | null>(
    null,
  );

  const handleEvidenceClick = (evidence: {
    page: number;
    text: string;
    box_2d?: number[];
  }) => {
    setEvidenceHighlight(evidence);
    if (evidence.box_2d) {
      const [ymin, xmin, ymax, xmax] = evidence.box_2d;
      // Convert 0-1000 normalized to 0-1
      const x = (xmin + xmax) / 2000;
      const y = (ymin + ymax) / 2000;
      setJumpTarget({ page: evidence.page, x, y });
    } else {
      setJumpTarget({ page: evidence.page, x: 0.5, y: 0.2 });
    }
  };
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [currentPaperId, setCurrentPaperId] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [initialPages, setInitialPages] = useState<PageData[] | undefined>(
    undefined,
  );

  const handleSelectPaper = async (paperId: string) => {
    setCurrentPaperId(paperId);
    setIsAnalyzing(true);
    setInitialPages(undefined);

    try {
      const headers: HeadersInit = {};
      const res = await fetch(`/papers/${paperId}`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.layout_json) {
          try {
            const layout = JSON.parse(data.layout_json);

            // Fetch figure IDs from backend
            let figureMap: Record<string, string> = {};
            try {
              const figRes = await fetch(`/api/papers/${paperId}/figures`);
              if (figRes.ok) {
                const figData = await figRes.json();
                (figData.figures || []).forEach((f: any) => {
                  // Key by page and bbox string for matching
                  const key = `${f.page_number}-${f.bbox.join(",")}`;
                  figureMap[key] = f.figure_id;
                });
              }
            } catch (e) {
              console.warn("Failed to fetch figures", e);
            }

            // Convert DB layout to PageData format
            const pages: PageData[] = layout.map((lp: any, idx: number) => {
              const pageNum = idx + 1;
              const figures = (lp?.figures || []).map((fig: any) => ({
                ...fig,
                id: figureMap[`${pageNum}-${fig.bbox.join(",")}`],
              }));

              return {
                page_num: pageNum,
                image_url: `/static/paper_images/${data.file_hash}/page_${pageNum}.png`,
                width: lp?.width || 0,
                height: lp?.height || 0,
                words: lp?.words || [],
                figures: figures,
              };
            });
            setInitialPages(pages);
          } catch (e) {
            console.error("Failed to parse layout_json", e);
          }
        }
      }
    } catch (e) {
      console.error("Failed to load paper", e);
    } finally {
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    const path = window.location.pathname;
    const match = path.match(/^\/(?:papers|reader|pdf)\/([a-z0-9-]+)/i);
    if (match && match[1]) {
      handleSelectPaper(match[1]);
    }
  }, []);

  useEffect(() => {
    if (user) {
      setShowLoginModal(false);
      fetch("/api/config")
        .then((res) => res.json())
        .then((data) => setConfig(data))
        .catch((err) => console.error(err));
    }
  }, [user]);

  const handlePaperLoaded = (paperId: string | null) => {
    setCurrentPaperId(paperId);
  };

  const handleAskAI = (prompt: string) => {
    setInitialChatMessage(prompt);
    setActiveTab("chat");
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setUploadFile(e.target.files[0]);
      setCurrentPaperId(null);
    }
  };

  const handleWordClick = (
    word: string,
    context?: string,
    coords?: { page: number; x: number; y: number },
  ) => {
    setSelectedWord(word);
    setSelectedContext(context);
    setSelectedCoordinates(coords);
    setActiveTab("dict");
  };

  const handleTextSelect = (
    text: string,
    coords: { page: number; x: number; y: number },
  ) => {
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

  const handleFigureClick = async (fig: any) => {
    if (!fig.id) {
      handleAskAI(
        t("chat.analyze_request", {
          type: fig.label || "図",
          defaultValue: `${fig.label || "図"}の解説をお願いします。`,
        }),
      );
      return;
    }

    // Show immediate feedback in chat
    const typeName = fig.label || "図";
    handleAskAI(t("chat.analyzing_figure", { type: typeName }));

    try {
      const res = await fetch(`/api/figures/${fig.id}/explain`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        handleAskAI(
          `### ${typeName}${t("chat.analysis_result_suffix", { defaultValue: "の解析結果" })}\n\n${data.explanation}`,
        );
      } else {
        handleAskAI(t("chat.analysis_failed", { type: typeName }));
      }
    } catch (e) {
      console.error("Figure analysis failed", e);
      handleAskAI(t("chat.analysis_error", { type: typeName }));
    }
  };

  const handleTableClick = async (table: any) => {
    // Tables might have table_content/markdown
    if (table.table_content) {
      handleAskAI(
        t("chat.table_explain_request", {
          defaultValue: "この表について解説してください:",
        }) + `\n\n${table.table_content}`,
      );
    } else if (table.id) {
      handleFigureClick(table);
    } else {
      handleAskAI(
        t("chat.table_generic_request", {
          defaultValue: "この表の解説をお願いします。",
        }),
      );
    }
  };

  const handleJumpToLocation = (page: number, x: number, y: number) => {
    setJumpTarget({ page, x, y });
  };

  const handleAnalysisStatusChange = (status: string) => {
    setIsAnalyzing(status === "uploading" || status === "processing");
  };

  return (
    <div className="flex h-screen w-full bg-gray-100 overflow-hidden">
      {/* Sidebar Placeholder */}
      <div className="w-72 bg-gray-900 text-white p-4 hidden md:flex flex-col border-r border-gray-800">
        <div className="flex items-center gap-3 mb-10 px-2">
          <div className="w-10 h-10 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <span className="text-2xl font-black italic text-white">T</span>
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tighter text-white">
              {t("app.title")}
            </h1>
            <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest leading-none">
              {t("app.tagline")}
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <PaperList
            onSelectPaper={handleSelectPaper}
            currentPaperId={currentPaperId}
          />
          {config && (
            <div className="px-4 py-2 mt-4">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                  {t("app.system_online")}
                </span>
              </div>
            </div>
          )}
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
                <p className="text-sm font-medium truncate">
                  {t("app.guest_user")}
                </p>
                <p className="text-xs text-gray-400 truncate">
                  {t("app.limited_access")}
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
              {t("app.sign_in")}
            </button>
          )}
        </div>

        <div className="mt-4">
          <label className="block text-xs font-bold mb-2 text-gray-400">
            {t("app.upload_pdf")}
          </label>
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
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full relative">
        <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 shadow-sm justify-between">
          <div className="flex items-center gap-4">
            <span className="font-semibold text-gray-700">
              {t("app.reading_mode")}
            </span>
            <select
              value={i18n.language}
              onChange={(e) => i18n.changeLanguage(e.target.value)}
              className="text-xs bg-slate-50 border border-slate-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-500 transition-all font-medium text-slate-600"
            >
              <option value="ja">日本語</option>
              <option value="en">English</option>
            </select>
          </div>
          {uploadFile && (
            <span className="text-sm text-gray-500">{uploadFile.name}</span>
          )}
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* PDF Viewer Area */}
          <div className="flex-1 bg-slate-100 flex items-center justify-center relative overflow-hidden">
            {uploadFile || initialPages ? (
              <div className="w-full h-full p-4 md:p-8 overflow-y-auto custom-scrollbar">
                <PDFViewer
                  sessionId={sessionId}
                  uploadFile={uploadFile}
                  initialData={initialPages}
                  onWordClick={handleWordClick}
                  onTextSelect={handleTextSelect}
                  onAreaSelect={handleAreaSelect}
                  jumpTarget={jumpTarget}
                  evidenceHighlight={evidenceHighlight}
                  onStatusChange={handleAnalysisStatusChange}
                  onPaperLoaded={handlePaperLoaded}
                  onAskAI={handleAskAI}
                  onFigureClick={handleFigureClick}
                  onTableClick={handleTableClick}
                />
              </div>
            ) : (
              <UploadZone
                onFileChange={(file: File) => {
                  setUploadFile(file);
                  setCurrentPaperId(null);
                }}
              />
            )}
          </div>

          {/* Right Sidebar */}
          <div className="w-96 h-full shadow-xl z-20 border-l border-gray-200 bg-white">
            <Sidebar
              sessionId={sessionId}
              activeTab={activeTab}
              onTabChange={setActiveTab}
              selectedWord={selectedWord}
              context={selectedContext}
              coordinates={selectedCoordinates}
              selectedImage={selectedImage}
              onJump={handleJumpToLocation}
              onEvidenceClick={handleEvidenceClick}
              isAnalyzing={isAnalyzing}
              initialChatMessage={initialChatMessage}
              onClearInitialChatMessage={() => setInitialChatMessage(null)}
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
    </div>
  );
}

export default App;

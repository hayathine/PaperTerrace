import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import { useTranslation } from "react-i18next";

import { PageData, PageWithLines } from "./types";
import PDFPage from "./PDFPage";
import StampPalette from "../Stamps/StampPalette";
import { Stamp, StampType } from "../Stamps/types";
import { useAuth } from "../../contexts/AuthContext";
import TextModeViewer from "./TextModeViewer";
import { groupWordsIntoLines } from "./utils";
import { usePaperCache } from "../../db/hooks";
import { useSyncStatus } from "../../db/sync";

interface PDFViewerProps {
  taskId?: string;
  initialData?: PageData[];
  uploadFile?: File | null;
  sessionId?: string;
  onWordClick?: (
    word: string,
    context?: string,
    coords?: { page: number; x: number; y: number },
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
    status: "idle" | "uploading" | "processing" | "done" | "error",
  ) => void;
  onPaperLoaded?: (paperId: string | null) => void;
  onAskAI?: (prompt: string) => void;
  paperId?: string | null;
}

const PDFViewer: React.FC<PDFViewerProps> = ({
  uploadFile,
  paperId: propPaperId,
  onWordClick,
  onTextSelect,
  onAreaSelect,
  sessionId,
  jumpTarget,
  onStatusChange,
  onPaperLoaded,
  onAskAI,
}) => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const { getCachedPaper, savePaperToCache, cachePaperImages } =
    usePaperCache();
  const syncStatus = useSyncStatus();
  const [pages, setPages] = useState<PageData[]>([]);
  const [status, setStatus] = useState<
    "idle" | "uploading" | "processing" | "done" | "error"
  >("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const eventSourceRef = useRef<EventSource | null>(null);
  const [loadedPaperId, setLoadedPaperId] = useState<string | null>(null);
  const processingFileRef = useRef<File | null>(null);
  const activeTaskIdRef = useRef<string | null>(null);

  // const containerRef = useRef<HTMLDivElement>(null); // Unused now

  // Stamp State
  // Modes: 'plaintext' (default), 'text', 'stamp', 'area'
  const [mode, setMode] = useState<"text" | "stamp" | "area" | "plaintext">(
    "plaintext",
  );
  const [stamps, setStamps] = useState<Stamp[]>([]);
  const [selectedStamp, setSelectedStamp] = useState<StampType>("👍");

  const pagesRef = useRef<PageData[]>([]);

  useEffect(() => {
    if (onStatusChange) {
      onStatusChange(status);
    }
  }, [status, onStatusChange]);

  // Sync ref with state
  useEffect(() => {
    pagesRef.current = pages;
  }, [pages]);

  useEffect(() => {
    if (uploadFile) {
      startAnalysis(uploadFile);
    } else if (propPaperId && propPaperId !== loadedPaperId) {
      loadExistingPaper(propPaperId);
    }
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [uploadFile, propPaperId]);

  // Fetch stamps when loadedPaperId is available
  useEffect(() => {
    if (loadedPaperId) {
      fetchStamps(loadedPaperId);
    }
    if (onPaperLoaded) {
      onPaperLoaded(loadedPaperId);
    }
  }, [loadedPaperId]);

  const fetchStamps = async (id: string) => {
    try {
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/stamps/paper/${id}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setStamps(data.stamps);
      }
    } catch (e) {
      console.error("Failed to fetch stamps", e);
    }
  };

  // Scroll to jump target when it changes
  useEffect(() => {
    if (jumpTarget) {
      const pageEl = document.getElementById(`page-${jumpTarget.page}`);
      if (pageEl) {
        // Find scrollable container (assuming one of the parents is overflow-y-auto)
        // In App.tsx it's the div with ".overflow-y-auto"
        const scroller = pageEl.closest(".overflow-y-auto");

        if (scroller) {
          const pageRect = pageEl.getBoundingClientRect();
          const scrollerRect = scroller.getBoundingClientRect();

          // Current scroll position
          const currentScrollTop = scroller.scrollTop;

          // pageRect.top is relative to viewport
          // We need offset from scroller top
          // scrollerRect.top is viewport top of scroller

          // Page top position inside the scrollable content
          const pageTopInScroller =
            currentScrollTop + (pageRect.top - scrollerRect.top);

          // Target Y within the page (height * percentage)
          const targetYInPage = pageRect.height * (jumpTarget.y || 0); // Default to top if y is missing

          // Center the target in the viewport (scroller height / 2)
          const targetScrollTop =
            pageTopInScroller + targetYInPage - scrollerRect.height / 2;

          scroller.scrollTo({
            top: targetScrollTop,
            behavior: "smooth",
          });

          // Also highlight the target location temporarily?
        } else {
          // Fallback if no specific scroller found (e.g. window scroll)
          pageEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
    }
  }, [jumpTarget]);

  const startAnalysis = async (file: File) => {
    if (processingFileRef.current === file) return;
    processingFileRef.current = file;

    setStatus("uploading");
    setPages([]);
    setLoadedPaperId(null);
    setStamps([]);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("lang", i18n.language);

    formData.append("mode", "json");
    if (sessionId) {
      formData.append("session_id", sessionId);
    }

    try {
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch("/analyze-pdf-json", {
        method: "POST",
        headers,
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Upload failed");
      }

      const data = await response.json();
      const { task_id, stream_url } = data;
      activeTaskIdRef.current = task_id;

      // Close existing if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      setStatus("processing");
      const es = new EventSource(stream_url);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const eventData = JSON.parse(event.data);
          console.debug("[PDFViewer] SSE Message:", eventData.type, eventData);

          if (eventData.type === "page") {
            setPages((prev) => {
              const newData = eventData.data;
              const index = prev.findIndex(
                (p) => p.page_num === newData.page_num,
              );
              if (index !== -1) {
                // Replace existing page data (update)
                const newPages = [...prev];
                newPages[index] = newData;
                return newPages;
              }
              // Append new page
              return [...prev, newData];
            });
          } else if (eventData.type === "done") {
            setStatus("done");
            if (eventData.paper_id) {
              const pId = eventData.paper_id;
              setLoadedPaperId(pId);

              // Use ref to get the latest pages collected during streaming
              const finalPages = pagesRef.current;

              // Cache the final results
              (async () => {
                const imageUrls = finalPages.map((p) => p.image_url);
                const ocrText = finalPages
                  .map((p) => p.content)
                  .join("\n\n---\n\n");
                const layoutData = finalPages.map((p) => ({
                  width: p.width,
                  height: p.height,
                  words: p.words,
                  figures: p.figures,
                  links: p.links,
                }));

                // Extract file_hash from image_url (e.g. /static/paper_images/{hash}/page_1.png)
                let fileHash = "";
                if (imageUrls.length > 0) {
                  const match = imageUrls[0].match(
                    /\/static\/paper_images\/([^/]+)\//,
                  );
                  if (match) fileHash = match[1];
                }

                await savePaperToCache({
                  id: pId,
                  file_hash: fileHash,
                  title: processingFileRef.current?.name || "Untitled",
                  ocr_text: ocrText,
                  layout_json: JSON.stringify(layoutData),
                  last_accessed: Date.now(),
                });
                // We don't block on image caching
                cachePaperImages(pId, imageUrls);
              })();
            }
            es.close();
          } else if (eventData.type === "error") {
            setStatus("error");
            setErrorMsg(eventData.message);
            es.close();
            processingFileRef.current = null;
            activeTaskIdRef.current = null;
          }
        } catch (e) {
          // Ignore
        }
      };

      es.onerror = (err) => {
        console.error("SSE Error", err);
        es.close();
        // If it fails immediately or without any pages, show error
        if (status === "processing" && pages.length === 0) {
          setStatus("error");
          setErrorMsg("Network error while streaming analysis");
        }
        processingFileRef.current = null;
        activeTaskIdRef.current = null;
      };
    } catch (err: any) {
      setStatus("error");
      setErrorMsg(err.message);
    }
  };

  const handleWordClick = useCallback(
    (
      word: string,
      context?: string,
      coords?: { page: number; x: number; y: number },
    ) => {
      if (onWordClick) {
        onWordClick(word, context, coords);
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

  const handleAreaSelect = useCallback(
    async (coords: {
      page: number;
      x: number;
      y: number;
      width: number;
      height: number;
    }) => {
      // Find page data
      const page = pages.find((p) => p.page_num === coords.page);
      if (!page || !onAreaSelect) return;

      try {
        // Load image for cropping
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.src = page.image_url;
        await new Promise((resolve) => (img.onload = resolve));

        const canvas = document.createElement("canvas");
        // Coords are in relative [0-1] format
        const cropX = coords.x * img.naturalWidth;
        const cropY = coords.y * img.naturalHeight;
        const cropW = coords.width * img.naturalWidth;
        const cropH = coords.height * img.naturalHeight;

        canvas.width = cropW;
        canvas.height = cropH;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        ctx.drawImage(img, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

        // Upload the cropped image
        canvas.toBlob(async (blob) => {
          if (!blob) return;
          const formData = new FormData();
          formData.append("file", blob, "crop.png");

          // We need token if auth is enabled
          const headers: HeadersInit = {};
          if (token) headers["Authorization"] = `Bearer ${token}`;

          const res = await fetch("/upload/image", {
            method: "POST",
            headers,
            body: formData,
          });

          if (res.ok) {
            const data = await res.json();
            onAreaSelect(data.url, {
              page: coords.page,
              x: coords.x,
              y: coords.y,
            });
            // Switch back to text mode after selection?
            setMode("text");
          }
        }, "image/png");
      } catch (e) {
        console.error("Failed to crop/upload image", e);
      }
    },
    [pages, onAreaSelect, token],
  );

  const handleAddStamp = useCallback(
    async (page: number, x: number, y: number) => {
      if (!loadedPaperId) {
        alert("Paper ID not found. Please wait for analysis to complete.");
        return;
      }

      const newStamp: Stamp = {
        id: "temp-" + Date.now(),
        type: selectedStamp,
        x,
        y,
        page_number: page,
      };

      // Optimistic update
      setStamps((prev) => [...prev, newStamp]);

      try {
        const headers: HeadersInit = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`/stamps/paper/${loadedPaperId}`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            stamp_type: selectedStamp,
            x,
            y,
            page_number: page,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          // Update ID from backend
          setStamps((prev) =>
            prev.map((s) =>
              s.id === newStamp.id ? { ...s, id: data.stamp_id } : s,
            ),
          );
        } else {
          console.error("Failed to save stamp");
          // Rollback?
          setStamps((prev) => prev.filter((s) => s.id !== newStamp.id));
        }
      } catch (e) {
        console.error("Error saving stamp", e);
      }
    },
    [loadedPaperId, selectedStamp, token],
  );

  const pagesWithLines: PageWithLines[] = useMemo(
    () => groupWordsIntoLines(pages),
    [pages],
  );

  const loadExistingPaper = async (id: string) => {
    setStatus("processing");
    setLoadedPaperId(id);
    setStamps([]);

    try {
      // 0. Check IndexedDB Cache First (Offline First / Fast Load)
      const cached = await getCachedPaper(id);
      if (cached && cached.layout_json && cached.file_hash) {
        console.log("[PDFViewer] Fast Load from cache:", id);
        try {
          const layoutList = JSON.parse(cached.layout_json);
          const ocrParts = (cached.ocr_text || "").split("\n\n---\n\n");
          const fileHash = cached.file_hash;

          const cachedPages: PageData[] = layoutList.map(
            (layout: any, i: number) => ({
              page_num: i + 1,
              image_url: `/static/paper_images/${fileHash}/page_${i + 1}.png`,
              width: layout?.width || 0,
              height: layout?.height || 0,
              words: layout?.words || [],
              figures: layout?.figures || [],
              links: layout?.links || [],
              content: ocrParts[i] || "",
            }),
          );

          if (cachedPages.length > 0) {
            setPages(cachedPages);
            setStatus("done");
            // If we have content, we could stop here.
            // Optional: Background check with server to ensure consistency.
            return;
          }
        } catch (e) {
          console.warn("[PDFViewer] Failed to parse cached data", e);
        }
      }

      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // 1. Try to fetch full paper data directly first (Fast Load)
      const paperRes = await fetch(`/papers/${id}`, { headers });
      if (paperRes.ok) {
        const paperData = await paperRes.json();

        // Save/Update cache with latest metadata
        await savePaperToCache({
          id: id,
          file_hash: paperData.file_hash || "",
          title: paperData.title || paperData.filename,
          ocr_text: paperData.ocr_text,
          layout_json: paperData.layout_json,
          full_summary: paperData.full_summary,
          section_summary_json: paperData.section_summary_json,
          last_accessed: Date.now(),
        });

        if (paperData.layout_json && paperData.file_hash) {
          try {
            const layoutList = JSON.parse(paperData.layout_json);
            const ocrParts = (paperData.ocr_text || "").split("\n\n---\n\n");
            const fileHash = paperData.file_hash;

            const fullPages: PageData[] = layoutList.map(
              (layout: any, i: number) => ({
                page_num: i + 1,
                image_url: `/static/paper_images/${fileHash}/page_${i + 1}.png`,
                width: layout?.width || 0,
                height: layout?.height || 0,
                words: layout?.words || [],
                figures: layout?.figures || [],
                links: layout?.links || [],
                content: ocrParts[i] || "",
              }),
            );

            if (fullPages.length > 0) {
              setPages(fullPages);
              setStatus("done");

              // Cache images in background
              cachePaperImages(
                id,
                fullPages.map((p) => p.image_url),
              );
              return; // Success! No need to stream.
            }
          } catch (parseErr) {
            console.warn(
              "Failed to parse cached layout, falling back to stream",
              parseErr,
            );
          }
        }
      }

      // 2. Fallback to streaming if not already processed/cached in a way we can use
      // If we are already displaying some pages, don't clear them until we get the first chunk from the new stream
      // to avoid a white flicker.
      // setPages([]); // Removed immediate clear
      const formData = new FormData();
      if (sessionId) formData.append("session_id", sessionId);

      const response = await fetch(`/analyze-paper/${id}`, {
        method: "POST",
        headers,
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to load paper");

      const data = await response.json();
      const { stream_url } = data;

      const es = new EventSource(stream_url);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const eventData = JSON.parse(event.data);
          if (eventData.type === "page") {
            setPages((prev) => {
              const newData = eventData.data;
              const index = prev.findIndex(
                (p) => p.page_num === newData.page_num,
              );
              if (index !== -1) {
                const newPages = [...prev];
                newPages[index] = newData;
                return newPages;
              }
              return [...prev, newData];
            });
          } else if (eventData.type === "done") {
            setStatus("done");
            es.close();
          } else if (eventData.type === "error") {
            setStatus("error");
            setErrorMsg(eventData.message);
            es.close();
          }
        } catch (e) {}
      };

      es.onerror = (err) => {
        console.error("SSE Error", err);
        es.close();
        if (pages.length === 0) setStatus("error"); // Only error if we got nothing
      };
    } catch (err: any) {
      setStatus("error");
      setErrorMsg(err.message);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto p-2 md:p-4 relative min-h-full pb-20">
      {status === "idle" && !uploadFile && !propPaperId && (
        <div className="text-center p-10 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
          {t("viewer.waiting_pdf")}
        </div>
      )}

      {status === "uploading" && (
        <div className="flex justify-center p-10">
          <span className="animate-pulse text-blue-500">
            {t("viewer.uploading_pdf")}
          </span>
        </div>
      )}

      {status === "error" && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
          Error: {errorMsg}
        </div>
      )}

      {/* Toolbar */}
      {pages.length > 0 && (
        <div className="sticky top-4 z-[60] flex justify-center mb-6">
          <div className="bg-white p-1 rounded-lg shadow-sm border border-slate-200 flex items-center gap-1">
            <div
              className="px-2 flex items-center gap-2 border-r border-slate-100 mr-1"
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
            <button
              onClick={() => setMode("plaintext")}
              className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                mode === "plaintext"
                  ? "bg-indigo-600 text-white shadow-none"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              <span className="text-sm">📝</span>
              <span className="hidden sm:inline">
                {t("viewer.toolbar.text_mode")}
              </span>
            </button>

            <button
              onClick={() => setMode("text")}
              className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                mode === "text"
                  ? "bg-indigo-600 text-white shadow-none"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              <span className="text-sm">📄</span>
              <span className="hidden sm:inline">
                {t("viewer.toolbar.click_mode")}
              </span>
            </button>

            <div className="w-[1px] h-4 bg-slate-200 mx-1 hidden sm:block" />
            <button
              onClick={() => setMode("area")}
              className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                mode === "area"
                  ? "bg-indigo-600 text-white shadow-none"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              <span className="text-sm">✂️</span>
              <span className="hidden sm:inline">
                {t("viewer.toolbar.area_mode")}
              </span>
            </button>

            <button
              onClick={() => setMode("stamp")}
              className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                mode === "stamp"
                  ? "bg-indigo-600 text-white shadow-none"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              <span className="text-sm">👍</span>
              <span className="hidden sm:inline">
                {t("viewer.toolbar.stamp_mode")}
              </span>
            </button>
          </div>
        </div>
      )}

      {/* Content Area */}
      <div className={mode === "plaintext" ? "block" : "hidden"}>
        <TextModeViewer
          pages={pagesWithLines}
          onWordClick={handleWordClick}
          onTextSelect={handleTextSelect}
          jumpTarget={jumpTarget}
        />
      </div>

      <div className={mode !== "plaintext" ? "block" : "hidden"}>
        <div
          className={`space-y-6 ${mode === "stamp" || mode === "area" ? "cursor-crosshair" : ""}`}
        >
          {pages.map((page) => (
            <PDFPage
              key={page.page_num}
              page={page}
              onWordClick={handleWordClick}
              onTextSelect={handleTextSelect}
              stamps={stamps}
              isStampMode={mode === "stamp"}
              onAddStamp={handleAddStamp}
              isAreaMode={mode === "area"}
              onAreaSelect={handleAreaSelect}
              onAskAI={onAskAI}
              jumpTarget={jumpTarget}
            />
          ))}
        </div>
      </div>

      {status === "processing" && (
        <div className="flex justify-center py-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {/* Stamp Palette (Only show if we have pages/loadedPaperId) */}
      {loadedPaperId && mode === "stamp" && (
        <StampPalette
          isStampMode={true}
          onToggleMode={() => setMode("text")}
          selectedStamp={selectedStamp}
          onSelectStamp={setSelectedStamp}
        />
      )}
    </div>
  );
};

export default PDFViewer;

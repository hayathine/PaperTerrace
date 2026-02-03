import React, { useMemo, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLiveQuery } from "dexie-react-hooks";
import { db } from "../../db";

import { PageData } from "./types";
import StampOverlay from "../Stamps/StampOverlay";
import BoxOverlay from "./BoxOverlay";
import { Stamp } from "../Stamps/types";

const getFigTypeLabel = (t: any, label: string): string => {
  const keyMap: Record<string, string> = {
    table: "pdf.table",
    figure: "pdf.figure",
    equation: "pdf.equation",
    image: "pdf.image",
  };
  const key = keyMap[label.toLowerCase()] || "pdf.figure";
  return t(key);
};

interface PDFPageProps {
  page: PageData;
  scale?: number;
  onWordClick?: (
    word: string,
    context?: string,
    coords?: { page: number; x: number; y: number },
  ) => void;
  onTextSelect?: (
    text: string,
    coords: { page: number; x: number; y: number },
  ) => void;
  // Stamp props
  stamps?: Stamp[];
  isStampMode?: boolean;
  onAddStamp?: (page: number, x: number, y: number) => void;
  // Area selection props
  isAreaMode?: boolean;
  onAreaSelect?: (coords: {
    page: number;
    x: number;
    y: number;
    width: number;
    height: number;
  }) => void;
  onAskAI?: (prompt: string) => void;
  jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
}

const PDFPage: React.FC<PDFPageProps> = ({
  page,
  onWordClick,
  onTextSelect,
  stamps = [],
  isStampMode = false,
  onAddStamp,
  isAreaMode = false,
  onAreaSelect,
  onAskAI,
  jumpTarget,
}) => {
  const { t } = useTranslation();
  const { width, height, words, figures, image_url, page_num } = page;

  // Check for cached image in IndexedDB
  const cachedImage = useLiveQuery(() => db.images.get(image_url), [image_url]);

  const [displayUrl, setDisplayUrl] = useState(image_url);

  useEffect(() => {
    if (cachedImage && cachedImage.blob) {
      const blobUrl = URL.createObjectURL(cachedImage.blob);
      setDisplayUrl(blobUrl);
      return () => {
        URL.revokeObjectURL(blobUrl);
      };
    } else {
      setDisplayUrl(image_url);
    }
  }, [cachedImage, image_url]);

  // Text Selection State
  const [isDragging, setIsDragging] = React.useState(false);
  const [selectionStart, setSelectionStart] = React.useState<number | null>(
    null,
  );
  const [selectionEnd, setSelectionEnd] = React.useState<number | null>(null);
  const [selectionMenu, setSelectionMenu] = React.useState<{
    x: number;
    y: number;
    text: string;
    context: string;
    coords: any;
  } | null>(null);

  const handleMouseUp = () => {
    if (isStampMode || isAreaMode) return;

    if (isDragging && selectionStart !== null && selectionEnd !== null) {
      setIsDragging(false);

      if (selectionStart !== selectionEnd) {
        // Multi-word selection -> Show Menu
        const min = Math.min(selectionStart, selectionEnd);
        const max = Math.max(selectionStart, selectionEnd);
        const selectedWords = words.slice(min, max + 1);
        const text = selectedWords.map((w) => w.word).join(" ");
        // Context: grab a bit more surrounding text? For now just the selected text as context + some padding
        const startCtx = Math.max(0, min - 10);
        const endCtx = Math.min(words.length, max + 10);
        const context = words
          .slice(startCtx, endCtx)
          .map((w) => w.word)
          .join(" ");

        // Calculate bounding box of selection for anchor

        // Position menu near the end of selection or center? Center is better.
        // We need pixel coordinates for the menu relative to the page container
        // bbox is [x1, y1, x2, y2] in PDF coordinates (unscaled if width/height match PDF)
        // BUT the words bbox in PageData are likely consistent with width/height.
        // In the render, we use percentages.
        // We want the menu to be absolute positioned in the div.
        // x1, y1 etc are relative to page 'width' and 'height'.

        // Let's use % for position
        const x1 = Math.min(...selectedWords.map((w) => w.bbox[0]));
        const y1 = Math.min(...selectedWords.map((w) => w.bbox[1]));
        const x2 = Math.max(...selectedWords.map((w) => w.bbox[2]));
        const y2 = Math.max(...selectedWords.map((w) => w.bbox[3]));

        const centerPctX = ((x1 + x2) / 2 / width) * 100;
        // Place it slightly above the selection
        const topPctY = (y1 / height) * 100;

        const centerX = (x1 + x2) / 2 / width;
        const centerY = (y1 + y2) / 2 / height;

        setSelectionMenu({
          x: centerPctX,
          y: topPctY,
          text,
          context,
          coords: { page: page_num, x: centerX, y: centerY },
        });
      } else {
        // Single click
        setSelectionStart(null);
        setSelectionEnd(null);
      }
    }
  };

  // Additional helper to clear selection on outside click
  React.useEffect(() => {
    const handleClickOutside = () => {
      if (selectionMenu) {
        setSelectionMenu(null);
        setSelectionStart(null);
        setSelectionEnd(null);
      }
    };

    if (selectionMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [selectionMenu]);

  // Filter stamps for this page
  const pageStamps = useMemo(() => {
    return stamps.filter((s) => s.page_number === page_num || !s.page_number);
  }, [stamps, page_num]);

  const handleAddStamp = (x: number, y: number) => {
    if (onAddStamp) {
      onAddStamp(page_num, x, y);
    }
  };

  return (
    <div
      id={`page-${page.page_num}`}
      className="relative mb-8 shadow-2xl rounded-xl overflow-hidden bg-white transition-all duration-300 border border-slate-200/50 mx-auto"
      style={{ maxWidth: "100%" }}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        if (isDragging) {
          setIsDragging(false);
          setSelectionStart(null);
          setSelectionEnd(null);
        }
      }}
    >
      {/* Header / Page Number */}
      <div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
          {t("viewer.page")} {page.page_num}
        </span>
      </div>

      {/* Image Container */}
      <div className="relative w-full">
        <img
          src={displayUrl}
          alt={`Page ${page.page_num}`}
          className="w-full h-auto block select-none"
          loading="lazy"
        />

        {/* Stamp Overlay */}
        <StampOverlay
          stamps={pageStamps}
          isStampMode={isStampMode}
          onAddStamp={handleAddStamp}
        />

        {/* Box Selection Overlay */}
        <BoxOverlay
          isActive={isAreaMode}
          onSelect={(rect) => {
            if (onAreaSelect) {
              onAreaSelect({
                page: page_num,
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
              });
            }
          }}
        />

        {/* Word Overlays */}
        <div className="absolute inset-0 w-full h-full z-10">
          {words.map((w, idx) => {
            const [x1, y1, x2, y2] = w.bbox;
            const w_width = x2 - x1;
            const w_height = y2 - y1;

            const left = (x1 / width) * 100;
            const top = (y1 / height) * 100;
            const styleW = (w_width / width) * 100;
            const styleH = (w_height / height) * 100;

            const isSelected =
              selectionStart !== null &&
              selectionEnd !== null &&
              ((idx >= selectionStart && idx <= selectionEnd) ||
                (idx >= selectionEnd && idx <= selectionStart));

            const centerX = (x1 + x2) / 2 / width;
            const centerY = (y1 + y2) / 2 / height;
            const cleanWord = w.word.replace(
              /^[.,;!?(){}[\]"']+|[.,;!?(){}[\]"']+$/g,
              "",
            );

            const isJumpHighlight =
              jumpTarget &&
              jumpTarget.page === page_num &&
              // Use a small epsilon for coordinate matching
              Math.abs(centerX - jumpTarget.x) < 0.005 &&
              Math.abs(centerY - jumpTarget.y) < 0.005;

            return (
              <div
                key={`${idx}`}
                className={`absolute rounded-sm group ${!isStampMode ? "cursor-pointer" : "pointer-events-none"} 
                                    ${!isStampMode && !isSelected && !isJumpHighlight ? "hover:bg-yellow-300/30" : ""} 
                                    ${isSelected ? "bg-indigo-500/30 border border-indigo-500/50" : ""}
                                    ${isJumpHighlight ? "bg-yellow-400/60 border-2 border-yellow-600 shadow-[0_0_15px_rgba(250,204,21,0.5)] z-20 animate-bounce-subtle" : ""}`}
                style={{
                  left: `${left}%`,
                  top: `${top}%`,
                  width: `${styleW}%`,
                  height: `${styleH}%`,
                }}
                onMouseDown={(e) => {
                  if (isStampMode || isAreaMode) return;
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(true);
                  setSelectionStart(idx);
                  setSelectionEnd(idx);
                  setSelectionMenu(null); // Hide menu on new select start
                }}
                onMouseEnter={() => {
                  if (isDragging && selectionStart !== null) {
                    setSelectionEnd(idx);
                  }
                }}
                onClick={(e) => {
                  e.stopPropagation(); // Stop propagation to document
                  if (!isStampMode && onWordClick) {
                    if (selectionStart === selectionEnd && !selectionMenu) {
                      const start = Math.max(0, idx - 50);
                      const end = Math.min(words.length, idx + 50);
                      const context = words
                        .slice(start, end)
                        .map((w) => w.word)
                        .join(" ");

                      const wordCenterX = (x1 + x2) / 2 / width;
                      const wordCenterY = (y1 + y2) / 2 / height;

                      onWordClick(cleanWord, context, {
                        page: page_num,
                        x: wordCenterX,
                        y: wordCenterY,
                      });
                    }
                  }
                }}
                title={w.word}
              />
            );
          })}
        </div>

        {/* Figure/Equation Overlays */}
        <div className="absolute inset-0 w-full h-full z-20 pointer-events-none">
          {figures?.map((fig, idx) => {
            const [x1, y1, x2, y2] = fig.bbox;
            // Avoid rendering empty bboxes (like [0,0,0,0] from some native extractions)
            if (x1 === 0 && y1 === 0 && x2 === 0 && y2 === 0) return null;

            const f_width = x2 - x1;
            const f_height = y2 - y1;

            const left = (x1 / width) * 100;
            const top = (y1 / height) * 100;
            const styleW = (f_width / width) * 100;
            const styleH = (f_height / height) * 100;

            return (
              <div
                key={`fig-${idx}`}
                className="absolute cursor-pointer pointer-events-auto border-2 border-transparent hover:border-indigo-500/40 hover:bg-indigo-500/5 transition-all rounded-lg group flex items-start justify-end p-2"
                style={{
                  left: `${left}%`,
                  top: `${top}%`,
                  width: `${styleW}%`,
                  height: `${styleH}%`,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (onAskAI) {
                    const typeName = getFigTypeLabel(t, fig.label || "");
                    onAskAI(t("chat.explain_fig", { type: typeName }));
                  }
                }}
                title={`${fig.label || "figure"} click to explain`}
              >
                <div className="hidden group-hover:flex items-center gap-2 bg-slate-900/90 backdrop-blur-md text-white text-[10px] px-3 py-2 rounded-xl shadow-2xl font-bold border border-white/20 transform scale-90 group-hover:scale-100 transition-all duration-300 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                  <div className="w-5 h-5 bg-indigo-500 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-3 h-3"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                    </svg>
                  </div>
                  <span>
                    {t("chat.explain_fig_btn", {
                      type: getFigTypeLabel(t, fig.label || ""),
                    })}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Link Overlays */}
        <div className="absolute inset-0 w-full h-full z-20 pointer-events-none">
          {page.links?.map((link, idx) => {
            const [x1, y1, x2, y2] = link.bbox;
            const l_width = x2 - x1;
            const l_height = y2 - y1;
            const left = (x1 / width) * 100;
            const top = (y1 / height) * 100;
            const styleW = (l_width / width) * 100;
            const styleH = (l_height / height) * 100;

            return (
              <button
                key={`link-${idx}`}
                className="absolute cursor-pointer pointer-events-auto border border-blue-400/0 hover:border-blue-400/50 hover:bg-blue-400/10 transition-all rounded-sm z-30"
                style={{
                  left: `${left}%`,
                  top: `${top}%`,
                  width: `${styleW}%`,
                  height: `${styleH}%`,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (onWordClick) {
                    onWordClick(link.url);
                  }
                  window.open(link.url, "_blank", "noopener,noreferrer");
                }}
                title={link.url}
              />
            );
          })}
        </div>

        {/* Selection Menu */}
        {selectionMenu && (
          <div
            className="absolute z-50 flex gap-1 bg-gray-900 text-white p-1.5 rounded-lg shadow-xl transform -translate-x-1/2 -translate-y-full"
            style={{
              left: `${selectionMenu.x}%`,
              top: `${selectionMenu.y}%`,
              marginTop: "-10px",
            }}
            onMouseDown={(e) => e.stopPropagation()} // Prevent closing on click
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (onWordClick)
                  onWordClick(
                    selectionMenu.text,
                    selectionMenu.context,
                    selectionMenu.coords,
                  );
                setSelectionMenu(null);
                setSelectionStart(null);
                setSelectionEnd(null);
              }}
              className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-700"
            >
              <span>文A</span> {t("menu.translate")}
            </button>

            <button
              onClick={(e) => {
                e.stopPropagation();
                if (onTextSelect)
                  onTextSelect(selectionMenu.text, selectionMenu.coords);
                setSelectionMenu(null);
                setSelectionStart(null);
                setSelectionEnd(null);
              }}
              className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors"
            >
              <span>📝</span> {t("menu.note")}
            </button>

            {/* Triangle arrow */}
            <div className="absolute left-1/2 bottom-0 w-2 h-2 bg-gray-900 transform -translate-x-1/2 translate-y-1/2 rotate-45"></div>
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(PDFPage);

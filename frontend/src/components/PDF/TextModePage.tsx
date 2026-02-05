import React from "react";
import { PageWithLines } from "./types";

interface TextModePageProps {
  page: PageWithLines;
  onWordClick?: (
    word: string,
    context?: string,
    coords?: { page: number; x: number; y: number },
  ) => void;
  onTextSelect?: (
    text: string,
    coords: { page: number; x: number; y: number },
  ) => void;
  jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
  // 検索関連props
  searchTerm?: string;
  currentSearchMatch?: { page: number; wordIndex: number } | null;
}

const TextModePage: React.FC<TextModePageProps> = ({
  page,
  onWordClick,
  onTextSelect,
  jumpTarget,
  searchTerm,
  currentSearchMatch,
}) => {
  const [imageError, setImageError] = React.useState(false);
  const [selectionMenu, setSelectionMenu] = React.useState<{
    x: number;
    y: number;
    text: string;
    coords: any;
  } | null>(null);

  const handleMouseUp = (e: React.MouseEvent) => {
    // Selection detection can be tricky, small delay ensures selection state is updated
    setTimeout(() => {
      const selection = window.getSelection();
      const selectionText = selection?.toString().trim();

      if (
        selection &&
        selection.rangeCount > 0 &&
        selectionText &&
        selectionText.length > 0
      ) {
        const rect = e.currentTarget.getBoundingClientRect();
        const range = selection.getRangeAt(0);
        const rangeRect = range.getBoundingClientRect();

        // Ensure we have a valid bounding box
        if (rangeRect.width === 0) return;

        const pageWidth = rect.width || 1;
        const pageHeight = rect.height || 1;

        const menuX =
          (((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth) *
          100;
        const menuY = ((rangeRect.top - rect.top) / pageHeight) * 100;

        const centerX =
          ((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth;
        const centerY =
          ((rangeRect.top + rangeRect.bottom) / 2 - rect.top) / pageHeight;

        setSelectionMenu({
          x: menuX,
          y: menuY,
          text: selectionText,
          coords: { page: page.page_num, x: centerX, y: centerY },
        });
      } else {
        setSelectionMenu(null);
      }
    }, 10);
  };

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if ((e.target as HTMLElement).closest(".selection-menu")) return;
      setSelectionMenu(null);
    };
    if (selectionMenu)
      document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [selectionMenu]);

  return (
    <div
      id={`text-page-${page.page_num}`}
      className="relative shadow-sm bg-white border border-slate-200 group mx-auto"
      style={{
        maxWidth: "100%",
        userSelect: "none",
        containerType: "inline-size",
      }}
      onMouseUp={handleMouseUp}
    >
      {/* Header */}
      <div className="bg-slate-50 border-b border-slate-200 px-4 py-1.5 flex justify-between items-center select-none">
        <span className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">
          Page {page.page_num}
        </span>
      </div>

      {/* Content Container */}
      <div className="relative w-full overflow-hidden min-h-[600px] bg-white">
        {!imageError ? (
          <>
            {/* PDF Image (Base Layer) */}
            <img
              src={page.image_url}
              alt={`Page ${page.page_num}`}
              className="w-full h-auto block select-none pointer-events-none"
              loading="lazy"
              onError={() => {
                console.warn('Image failed to load:', page.image_url);
                setImageError(true);
              }}
              onLoad={() => {
                setImageError(false);
              }}
            />

            {/* Transparent Text Layer (Overlay Layer) */}
            <div
              className="absolute inset-0 z-10 w-full h-full cursor-text selection:bg-indigo-600/30"
              style={{ userSelect: "text" }}
            >
              {(() => {
                // グローバルwordインデックスを計算するためのカウンター
                let globalWordIndex = 0;

                return page.lines.map((line, lIdx) => {
                  const [lx1, ly1, lx2, ly2] = line.bbox;
                  const pWidth = page.width || 1;
                  const pHeight = page.height || 1;
                  const lTop = (ly1 / pHeight) * 100;
                  const lLeft = (lx1 / pWidth) * 100;
                  const lWidth = ((lx2 - lx1) / pWidth) * 100;
                  const lHeight = ((ly2 - ly1) / pHeight) * 100;

                  return (
                    <div
                      key={lIdx}
                      className="absolute text-transparent whitespace-pre flex items-center hover:text-slate-800 hover:bg-white/80 transition-colors duration-200"
                      style={{
                        top: `${lTop}%`,
                        left: `${lLeft}%`,
                        width: `${lWidth}%`,
                        height: `${lHeight}%`,
                        fontSize: `${lHeight * 0.8}cqw`,
                        letterSpacing: "-0.05em",
                      }}
                    >
                      {line.words.map((w, wIdx) => {
                        const currentGlobalIndex = globalWordIndex++;

                        const isJumpHighlight =
                          jumpTarget &&
                          jumpTarget.page === page.page_num &&
                          jumpTarget.term &&
                          w.word
                            .toLowerCase()
                            .includes(jumpTarget.term.toLowerCase());

                        // 検索マッチのハイライト
                        const isSearchMatch =
                          searchTerm &&
                          searchTerm.length >= 2 &&
                          w.word.toLowerCase().includes(searchTerm.toLowerCase());

                        // 現在フォーカスされている検索マッチかどうか
                        const isCurrentSearchMatch =
                          currentSearchMatch &&
                          currentSearchMatch.page === page.page_num &&
                          currentSearchMatch.wordIndex === currentGlobalIndex;

                        return (
                          <span
                            key={wIdx}
                            className={`transition-all 
                              ${isJumpHighlight ? "bg-yellow-400/40 border-b border-yellow-600" : ""}
                              ${isSearchMatch && !isCurrentSearchMatch ? "bg-amber-300/50 rounded" : ""}
                              ${isCurrentSearchMatch ? "bg-orange-500/60 rounded ring-2 ring-orange-400" : ""}`}
                            style={{ pointerEvents: "auto" }}
                          >
                            {w.word}{" "}
                          </span>
                        );
                      })}
                    </div>
                  );
                });
              })()}
            </div>
          </>
        ) : (
          /* Fallback: Text-only display when image fails to load */
          <div className="p-8 bg-gray-50 min-h-[600px]">
            <div className="prose max-w-none">
              <h3 className="text-lg font-semibold mb-4 text-gray-700">
                Page {page.page_num} - Text Content
              </h3>
              <div className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                {page.lines.map((line, lIdx) => (
                  <div key={lIdx} className="mb-2">
                    {line.words.map((w, wIdx) => {
                      const isJumpHighlight =
                        jumpTarget &&
                        jumpTarget.page === page.page_num &&
                        jumpTarget.term &&
                        w.word
                          .toLowerCase()
                          .includes(jumpTarget.term.toLowerCase());

                      const isSearchMatch =
                        searchTerm &&
                        searchTerm.length >= 2 &&
                        w.word.toLowerCase().includes(searchTerm.toLowerCase());

                      return (
                        <span
                          key={wIdx}
                          className={`${isJumpHighlight ? "bg-yellow-400/60 px-1 rounded" : ""} ${isSearchMatch ? "bg-amber-300/60 px-1 rounded" : ""}`}
                          onClick={() => {
                            if (onWordClick) {
                              onWordClick(w.word, undefined, {
                                page: page.page_num,
                                x: 0.5,
                                y: 0.5,
                              });
                            }
                          }}
                          style={{ cursor: "pointer" }}
                        >
                          {w.word}{" "}
                        </span>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Selection Menu */}
      {selectionMenu && (
        <div
          className="selection-menu absolute z-50 flex gap-0 bg-slate-900 text-white rounded shadow-lg overflow-hidden transform -translate-x-1/2 -translate-y-full border border-slate-800"
          style={{
            left: `${selectionMenu.x}%`,
            top: `${selectionMenu.y}%`,
            marginTop: "-10px",
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (onWordClick)
                onWordClick(
                  selectionMenu.text,
                  undefined,
                  selectionMenu.coords,
                );
              setSelectionMenu(null);
            }}
            className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-800"
          >
            <span>文A</span> Translate
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (onTextSelect)
                onTextSelect(selectionMenu.text, selectionMenu.coords);
              setSelectionMenu(null);
            }}
            className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors"
          >
            <span>📝</span> Note
          </button>
        </div>
      )}
    </div>
  );
};

export default React.memo(TextModePage);

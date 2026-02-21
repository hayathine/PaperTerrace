import React from "react";
import { PageWithLines } from "./types";
import TextModePage from "./TextModePage";

interface TextModeViewerProps {
  pages: PageWithLines[];
  onWordClick?: (
    word: string,
    context?: string,
    coords?: { page: number; x: number; y: number },
  ) => void;
  onTextSelect?: (
    text: string,
    coords: { page: number; x: number; y: number },
  ) => void;
  onAskAI?: (prompt: string) => void;
  jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
  searchTerm?: string;
  currentSearchMatch?: { page: number; wordIndex: number } | null;
}

const TextModeViewer: React.FC<TextModeViewerProps> = ({
  pages,
  onWordClick,
  onTextSelect,
  onAskAI,
  jumpTarget,
  searchTerm,
  currentSearchMatch,
}) => {
  if (!pages || pages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-400">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-4"></div>
        <p>読み込み中...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto p-4 space-y-12 pb-32">
      {pages.map((page) => (
        <TextModePage
          key={page.page_num}
          page={page}
          onWordClick={onWordClick}
          onTextSelect={onTextSelect}
          onAskAI={onAskAI}
          jumpTarget={jumpTarget}
          searchTerm={searchTerm}
          currentSearchMatch={currentSearchMatch}
        />
      ))}
    </div>
  );
};

export default React.memo(TextModeViewer);

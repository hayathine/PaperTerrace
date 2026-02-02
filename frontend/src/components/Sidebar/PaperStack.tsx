import React from "react";
import { useTranslation } from "react-i18next";

interface PaperStackProps {
  papers: { url: string; title?: string; addedAt: number }[];
  onRemove: (url: string) => void;
}

const PaperStack: React.FC<PaperStackProps> = ({ papers, onRemove }) => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col h-full bg-white font-sans">
      <div className="p-4 border-b border-slate-100 bg-slate-50">
        <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
          <svg
            className="w-4 h-4 text-indigo-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            />
          </svg>
          {t("stack.title")}
        </h3>

        <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-wider">
          Reading Stack
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {papers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-slate-300">
            <svg
              className="w-12 h-12 mb-2 opacity-20"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M12 6v6m0 0v6m0-6h6m-6 0H6"
              />
            </svg>
            <p className="text-sm">{t("stack.hint")}</p>
          </div>
        ) : (
          papers
            .sort((a, b) => b.addedAt - a.addedAt)
            .map((paper, idx) => (
              <div
                key={idx}
                className="group relative bg-slate-50 hover:bg-white hover:shadow-md border border-slate-100 rounded-lg p-3 transition-all duration-200"
              >
                <div className="pr-6">
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-indigo-600 hover:text-indigo-700 break-all line-clamp-2"
                  >
                    {paper.title || paper.url}
                  </a>
                  <p className="text-[10px] text-slate-400 mt-1">
                    {t("stack.added_at")}{" "}
                    {new Date(paper.addedAt).toLocaleString()}
                  </p>
                </div>

                <button
                  onClick={() => onRemove(paper.url)}
                  className="absolute top-3 right-3 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all p-1"
                  title="Remove from stack"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            ))
        )}
      </div>
    </div>
  );
};

export default PaperStack;

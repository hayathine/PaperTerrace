import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../contexts/AuthContext";

interface Paper {
  paper_id: string;
  filename: string;
  created_at: string;
}

interface PaperListProps {
  onSelectPaper: (paperId: string) => void;
  currentPaperId?: string | null;
}

const PaperList: React.FC<PaperListProps> = ({
  onSelectPaper,
  currentPaperId,
}) => {
  const { t } = useTranslation();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const { token } = useAuth();

  useEffect(() => {
    fetchPapers();
  }, []);

  const fetchPapers = async () => {
    try {
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/papers", { headers });
      if (res.ok) {
        const data = await res.json();
        setPapers(data.papers || []);
      }
    } catch (e) {
      console.error("Failed to fetch papers", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading)
    return (
      <div className="p-4 text-gray-500 text-xs animate-pulse">
        {t("library.loading")}
      </div>
    );

  return (
    <div className="flex flex-col gap-2 p-2">
      <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2 px-2">
        {t("library.title")}
      </h2>
      {papers.length === 0 ? (
        <p className="text-xs text-gray-500 px-2">{t("library.no_papers")}</p>
      ) : (
        <div className="flex flex-col gap-1 overflow-y-auto max-h-[60vh]">
          {papers.map((paper) => (
            <button
              key={paper.paper_id}
              onClick={() => onSelectPaper(paper.paper_id)}
              className={`text-left p-3 rounded-xl transition-all group relative overflow-hidden ${
                currentPaperId === paper.paper_id
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-200"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              }`}
            >
              <div className="flex items-start gap-3">
                <div
                  className={`mt-1 w-2 h-2 rounded-full shrink-0 ${
                    currentPaperId === paper.paper_id
                      ? "bg-white animate-pulse"
                      : "bg-indigo-500"
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate leading-tight">
                    {paper.filename}
                  </p>
                  <p
                    className={`text-[10px] mt-1 ${
                      currentPaperId === paper.paper_id
                        ? "text-indigo-100"
                        : "text-gray-500"
                    }`}
                  >
                    {new Date(paper.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              {/* Decorative background element for active item */}
              {currentPaperId === paper.paper_id && (
                <div className="absolute top-0 right-0 -mr-4 -mt-4 w-16 h-16 bg-white/10 rounded-full blur-2xl" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default PaperList;

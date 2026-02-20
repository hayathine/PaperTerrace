import React from "react";
import { useLoading } from "../../contexts/LoadingContext";
import { useTranslation } from "react-i18next";

const GlobalLoading: React.FC = () => {
  const { isLoading, message } = useLoading();
  const { t } = useTranslation();

  if (!isLoading) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[9999] pointer-events-none transition-all duration-300">
      <div className="flex items-center gap-4 p-4 pr-6 rounded-2xl bg-white shadow-2xl border border-slate-100 pointer-events-auto animate-in slide-in-from-bottom-8 fade-in zoom-in-95 duration-300">
        {/* Modern Animated Icon */}
        <div className="relative w-10 h-10 flex-shrink-0">
          <div className="absolute inset-0 rounded-full border-[3px] border-indigo-100"></div>
          <div className="absolute inset-0 rounded-full border-[3px] border-indigo-600 border-t-transparent animate-spin"></div>
          <div className="absolute inset-2 rounded-full bg-indigo-50 animate-pulse flex items-center justify-center">
            <svg
              className="w-3.5 h-3.5 text-indigo-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
                d="M12 6v6m0 0v6m0-6h6m-6 0H6"
              />
            </svg>
          </div>
        </div>

        {/* Text */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-800">
              {message || t("common.preparing")}
            </h3>
            {/* Subtle decorative dots */}
            <div className="mt-1 flex gap-1">
              <div className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]"></div>
              <div className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]"></div>
              <div className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce"></div>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 font-medium">
            {t("common.loading_description")}
          </p>
        </div>
      </div>
    </div>
  );
};

export default GlobalLoading;

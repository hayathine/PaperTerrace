import React from "react";
import { useLoading } from "../../contexts/LoadingContext";
import { useTranslation } from "react-i18next";

const GlobalLoading: React.FC = () => {
  const { isLoading, message } = useLoading();
  const { t } = useTranslation();

  if (!isLoading) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-white/60 backdrop-blur-md transition-all duration-300">
      <div className="flex flex-col items-center p-8 rounded-2xl bg-white shadow-2xl border border-slate-100 animate-in fade-in zoom-in duration-300">
        {/* Modern Animated Icon */}
        <div className="relative w-16 h-16 mb-6">
          <div className="absolute inset-0 rounded-full border-4 border-indigo-100"></div>
          <div className="absolute inset-0 rounded-full border-4 border-indigo-600 border-t-transparent animate-spin"></div>
          <div className="absolute inset-4 rounded-full bg-indigo-50 animate-pulse flex items-center justify-center">
            <svg
              className="w-5 h-5 text-indigo-600"
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
        <div className="text-center">
          <h3 className="text-lg font-bold text-slate-800 mb-1">
            {message || t("common.preparing")}
          </h3>
          <p className="text-sm text-slate-500 font-medium">
            {t("common.loading_description")}
          </p>
        </div>

        {/* Subtle decorative elements */}
        <div className="mt-8 flex gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]"></div>
          <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]"></div>
          <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce"></div>
        </div>
      </div>
    </div>
  );
};

export default GlobalLoading;

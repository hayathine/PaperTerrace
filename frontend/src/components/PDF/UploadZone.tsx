import React, { useRef } from "react";
import { useTranslation } from "react-i18next";

interface UploadZoneProps {
  onFileChange: (file: File) => void;
}

const UploadZone: React.FC<UploadZoneProps> = ({ onFileChange }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleContainerClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onFileChange(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type === "application/pdf") {
        onFileChange(file);
      } else {
        alert(t("pdf.alert_pdf_only"));
      }
    }
  };

  return (
    <div className="flex items-center justify-center p-4">
      <div
        onClick={handleContainerClick}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className="group relative w-full max-w-xl cursor-pointer"
      >
        {/* Background Glow Effect */}
        <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>

        <div className="relative flex flex-col items-center justify-center bg-white border-2 border-dashed border-slate-200 hover:border-indigo-400 rounded-2xl p-16 transition-all duration-300 shadow-xl shadow-slate-200/50">
          <div className="w-20 h-20 bg-indigo-50 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
            <svg
              className="w-10 h-10 text-indigo-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>

          <h2 className="text-2xl font-bold text-slate-800 mb-2">
            {t("pdf.upload_title")}
          </h2>
          <p className="text-slate-500 text-center max-w-sm mb-8">
            {t("pdf.upload_subtitle")}
          </p>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="px-6 py-2.5 bg-slate-900 text-white font-semibold rounded-full hover:bg-slate-800 transition-colors shadow-lg shadow-slate-900/10">
            {t("pdf.select_file")}
          </div>

          <div className="mt-8 flex gap-4 text-xs font-medium text-slate-400">
            <div className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              {t("pdf.fast_analysis")}
            </div>
            <div className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              {t("pdf.ai_explanation")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadZone;

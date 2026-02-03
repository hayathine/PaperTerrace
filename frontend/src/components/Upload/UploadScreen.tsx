import React, { useState, useCallback, useRef } from "react";

interface UploadScreenProps {
  onFileSelect: (file: File) => void;
}

const UploadScreen: React.FC<UploadScreenProps> = ({ onFileSelect }) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        const file = e.dataTransfer.files[0];
        if (file.type === "application/pdf") {
          onFileSelect(file);
        } else {
          alert("PDFファイルのみアップロード可能です。");
        }
      }
    },
    [onFileSelect],
  );

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0]);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center w-full h-full p-6 select-none animate-fade-in-up">
      {/* Brand Section */}
      <div className="mb-10 text-center relative group">
        <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-lg blur opacity-20 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
        <div className="relative">
          <h1 className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 mb-2 tracking-tight">
            PaperTerrace
          </h1>
          <p className="text-gray-500 text-lg font-light tracking-widest uppercase">
            Intellectual & Relaxed
          </p>
        </div>
      </div>

      {/* Upload Zone */}
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative w-full max-w-2xl aspect-[16/9] md:aspect-[21/9]
          flex flex-col items-center justify-center
          border-2 border-dashed rounded-3xl
          transition-all duration-300 ease-out
          cursor-pointer overflow-hidden
          group
          ${
            isDragging
              ? "border-indigo-500 bg-indigo-50/80 scale-[1.02] shadow-xl shadow-indigo-200/50"
              : "border-slate-300 bg-white/60 hover:border-indigo-400 hover:bg-white hover:shadow-2xl hover:shadow-indigo-100/50"
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={handleFileInput}
          className="hidden"
        />

        {/* Dynamic Background Pattern */}
        <div className="absolute inset-0 opacity-[0.03] group-hover:opacity-[0.06] transition-opacity duration-500">
          <svg className="w-full h-full" width="100%" height="100%">
            <pattern
              id="pattern-circles"
              x="0"
              y="0"
              width="20"
              height="20"
              patternUnits="userSpaceOnUse"
            >
              <circle
                cx="2"
                cy="2"
                r="1"
                className="text-current"
                fill="currentColor"
              />
            </pattern>
            <rect
              x="0"
              y="0"
              width="100%"
              height="100%"
              fill="url(#pattern-circles)"
            />
          </svg>
        </div>

        <div className="z-10 flex flex-col items-center space-y-6 p-8">
          <div
            className={`
            p-5 rounded-full 
            transition-all duration-300 
            ${
              isDragging
                ? "bg-indigo-100 text-indigo-600 scale-110 rotate-12"
                : "bg-slate-100 text-slate-400 group-hover:bg-indigo-50 group-hover:text-indigo-500 group-hover:-translate-y-1"
            }
          `}
          >
            <svg
              className="w-10 h-10"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>

          <div className="text-center">
            <h3
              className={`text-2xl font-bold transition-colors duration-300 ${
                isDragging
                  ? "text-indigo-700"
                  : "text-slate-700 group-hover:text-slate-900"
              }`}
            >
              PDFをドロップして読み込み
            </h3>
            <p className="mt-2 text-slate-500 font-medium">
              またはクリックしてファイルを選択
            </p>
          </div>

          <div className="mt-2 flex gap-3">
            <span className="px-3 py-1 bg-slate-100 text-slate-500 text-xs font-semibold rounded-full border border-slate-200 uppercase tracking-wide">
              English Support
            </span>
            <span className="px-3 py-1 bg-slate-100 text-slate-500 text-xs font-semibold rounded-full border border-slate-200 uppercase tracking-wide">
              Fast Analysis
            </span>
          </div>
        </div>
      </div>

      <p className="mt-8 text-xs text-slate-400 max-w-md text-center leading-relaxed">
        ※現在、英語の論文のみサポートしています。
        <br />
        アップロードされたファイルは安全に処理され、解析後に破棄されます。
      </p>
    </div>
  );
};

export default UploadScreen;

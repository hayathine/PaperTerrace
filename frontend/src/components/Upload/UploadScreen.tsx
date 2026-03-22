import type React from "react";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ERROR_KEYS } from "@/lib/errors";

interface UploadScreenProps {
	onFileSelect: (file: File) => void;
}

const UploadScreen: React.FC<UploadScreenProps> = ({ onFileSelect }) => {
	const { t } = useTranslation();
	const [isDragging, setIsDragging] = useState(false);
	const [fileTypeError, setFileTypeError] = useState<string | null>(null);
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

			if (e.dataTransfer.files?.[0]) {
				const file = e.dataTransfer.files[0];
				if (file.type === "application/pdf") {
					setFileTypeError(null);
					onFileSelect(file);
				} else {
					setFileTypeError(t(ERROR_KEYS.common.fileTypeInvalid));
				}
			}
		},
		[onFileSelect],
	);

	const handleClick = () => {
		fileInputRef.current?.click();
	};

	const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
		if (e.target.files?.[0]) {
			onFileSelect(e.target.files[0]);
		}
	};

	return (
		<div className="flex flex-col items-center justify-center w-full h-full p-6 select-none animate-fade-in-up">
			{/* Brand Section */}
			<div className="mb-6 text-center relative group">
				<div className="absolute -inset-1 bg-gradient-to-r from-orange-500 via-amber-500 to-pink-500 rounded-lg blur opacity-15 group-hover:opacity-30 transition duration-1000 group-hover:duration-200"></div>
				<div className="relative">
					<h1 className="text-[clamp(1.75rem,4vw,2.5rem)] font-black text-transparent bg-clip-text bg-gradient-to-r from-orange-500 to-amber-500 mb-1 tracking-tight leading-none">
						PaperTerrace
					</h1>
					<p className="text-gray-500 text-[clamp(0.7rem,1.1vw,0.8rem)] font-light tracking-[0.3em] uppercase">
						Intellectual & Relaxed
					</p>
				</div>
			</div>

			{/* Upload Zone */}
			<button
				type="button"
				onClick={handleClick}
				onKeyDown={(e) => {
					if (e.key === "Enter" || e.key === " ") {
						handleClick();
					}
				}}
				onDragOver={handleDragOver}
				onDragLeave={handleDragLeave}
				onDrop={handleDrop}
				className={`
          relative w-full max-w-2xl min-h-[clamp(240px,35vh,340px)]
          flex flex-col items-center justify-center
          border-2 border-dashed rounded-[clamp(1rem,1.5vw,1.5rem)]
          transition-all duration-300 ease-out
          cursor-pointer overflow-hidden
          group text-left
          ${
						isDragging
							? "border-orange-400 bg-orange-50/80 scale-[1.01] shadow-xl shadow-orange-200/50"
							: "border-slate-300 bg-white/60 hover:bg-white hover:shadow-2xl"
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

				<div className="z-10 flex flex-col items-center space-y-4 p-8">
					<div
						className={`
            p-3.5 rounded-full 
            transition-all duration-300 
            ${
							isDragging
								? "bg-orange-100 text-orange-500 scale-110 rotate-12"
								: "bg-slate-100 text-slate-400 group-hover:bg-slate-50 group-hover:text-slate-600 group-hover:-translate-y-1"
						}
          `}
					>
						<svg
							className="w-[clamp(1.75rem,5vw,2.5rem)] h-[clamp(1.75rem,5vw,2.5rem)]"
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
							className={`text-[clamp(1rem,2.5vw,1.5rem)] font-extrabold transition-colors duration-300 ${
								isDragging
									? "text-orange-600"
									: "text-slate-700 group-hover:text-slate-900"
							}`}
						>
							PDFをドロップして読み込み
						</h3>
						<p className="mt-1 text-slate-500 text-[clamp(0.75rem,1.3vw,0.875rem)] font-medium">
							またはクリックしてファイルを選択
						</p>
					</div>
				</div>

				<div className="mt-1 flex gap-[clamp(0.4rem,1.2vw,0.8rem)]">
					<span className="px-[clamp(0.4rem,1.2vw,0.8rem)] py-1 bg-slate-100 text-slate-400 text-[clamp(0.55rem,1.2vw,0.65rem)] font-bold rounded-full border border-slate-200 uppercase tracking-wider">
						English Support
					</span>
					<span className="px-[clamp(0.4rem,1.2vw,0.8rem)] py-1 bg-slate-100 text-slate-400 text-[clamp(0.55rem,1.2vw,0.65rem)] font-bold rounded-full border border-slate-200 uppercase tracking-wider">
						Fast Analysis
					</span>
				</div>
			</button>

			{fileTypeError && (
				<p className="mt-4 text-xs text-red-500 font-medium">{fileTypeError}</p>
			)}
		</div>
	);
};

export default UploadScreen;

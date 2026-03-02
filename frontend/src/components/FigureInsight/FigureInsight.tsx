import { useState } from "react";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import CopyButton from "../Common/CopyButton";
import MarkdownContent from "../Common/MarkdownContent";
import type { SelectedFigure } from "../PDF/types";

const log = createLogger("FigureInsight");

interface FigureInsightProps {
	selectedFigure?: SelectedFigure | null;
}

const FigureInsight: React.FC<FigureInsightProps> = ({ selectedFigure }) => {
	const [explanation, setExplanation] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(false);
	const [zoomedImage, setZoomedImage] = useState<string | null>(null);

	// 図が切り替わったら解説をリセット
	const figureKey = selectedFigure?.image_url ?? null;
	const [prevKey, setPrevKey] = useState<string | null>(null);
	if (figureKey !== prevKey) {
		setPrevKey(figureKey);
		setExplanation(null);
	}

	const handleExplain = async () => {
		if (!selectedFigure?.id) return;
		setIsLoading(true);
		try {
			const res = await fetch(
				`${API_URL}/api/figures/${selectedFigure.id}/explain`,
				{ method: "POST" },
			);
			if (res.ok) {
				const data = await res.json();
				setExplanation(data.explanation ?? null);
			}
		} catch (e) {
			log.error("handle_explain", "Failed to explain figure", {
				figureId: selectedFigure.id,
				error: e,
			});
		} finally {
			setIsLoading(false);
		}
	};

	if (!selectedFigure) {
		return (
			<div className="text-center py-16 px-6">
				<div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-4 border border-slate-100">
					<svg
						className="w-8 h-8 text-slate-300"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="1.5"
							d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
						/>
					</svg>
				</div>
				<h4 className="text-xs font-bold text-slate-500 mb-1">
					図をクリックして解説
				</h4>
				<p className="text-[10px] text-slate-400 leading-relaxed">
					クリックモードで論文中の図・表をクリックすると、ここに表示されます。
				</p>
			</div>
		);
	}

	return (
		<div className="relative">
			{/* 選択された図 */}
			<div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
				{/* 画像エリア */}
				<button
					type="button"
					onClick={() =>
						selectedFigure.image_url && setZoomedImage(selectedFigure.image_url)
					}
					className="relative w-full bg-slate-100 aspect-video flex items-center justify-center overflow-hidden border-b border-slate-100 cursor-zoom-in group/img border-none p-0"
				>
					<img
						src={
							selectedFigure.image_url.startsWith("http")
								? selectedFigure.image_url
								: `${API_URL}${selectedFigure.image_url}`
						}
						alt={`Figure on page ${selectedFigure.page_number}`}
						className="max-w-full max-h-full object-contain transition-transform group-hover/img:scale-105"
					/>
					<div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/5 transition-colors flex items-center justify-center">
						<div className="opacity-0 group-hover/img:opacity-100 transition-opacity bg-white/90 p-2 rounded-full shadow-lg text-orange-600">
							<svg
								className="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
								/>
							</svg>
						</div>
					</div>
					<div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm">
						P.{selectedFigure.page_number}
					</div>
					{selectedFigure.label && selectedFigure.label !== "image" && (
						<div className="absolute top-2 right-2 bg-orange-600/80 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm uppercase">
							{selectedFigure.label}
						</div>
					)}
				</button>

				{/* キャプション */}
				{selectedFigure.caption && (
					<p className="px-4 pt-3 text-[10px] text-slate-500 leading-relaxed border-b border-slate-100 pb-3">
						{selectedFigure.caption}
					</p>
				)}

				{/* 解説エリア */}
				<div className="p-4">
					{explanation ? (
						<div className="text-xs text-slate-600 leading-relaxed">
							<div className="flex justify-between items-center mb-1">
								<span className="font-bold text-orange-600 text-[10px] uppercase tracking-wider">
									Analysis
								</span>
								<CopyButton text={explanation} size={12} />
							</div>
							<MarkdownContent className="prose prose-xs max-w-none text-xs text-slate-600 leading-relaxed">
								{explanation}
							</MarkdownContent>
						</div>
					) : (
						<div className="flex flex-col items-center justify-center py-2">
							<button
								type="button"
								onClick={handleExplain}
								disabled={!selectedFigure.id || isLoading}
								className="flex items-center space-x-2 px-4 py-2 bg-orange-50 hover:bg-orange-100 text-orange-600 rounded-lg text-[11px] font-bold transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
							>
								{isLoading ? (
									<>
										<div className="w-3.5 h-3.5 border-2 border-orange-300 border-t-orange-600 rounded-full animate-spin" />
										<span>AIが解析中...</span>
									</>
								) : (
									<>
										<svg
											className="w-3.5 h-3.5"
											fill="currentColor"
											viewBox="0 0 20 20"
										>
											<path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
											<path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
										</svg>
										<span>AIに解説させる</span>
									</>
								)}
							</button>
							{!selectedFigure.id && (
								<p className="text-[10px] text-slate-400 mt-2">
									この図のIDが取得できないため解説できません。
								</p>
							)}
						</div>
					)}
				</div>
			</div>

			{/* Zoom Modal */}
			{zoomedImage && (
				<button
					type="button"
					className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4 md:p-8 border-none w-full h-full text-left"
					onClick={() => setZoomedImage(null)}
					onKeyDown={(e) => {
						if (e.key === "Escape") setZoomedImage(null);
					}}
				>
					<button
						type="button"
						className="absolute top-6 right-6 text-white/70 hover:text-white p-2 hover:bg-white/10 rounded-full transition-all"
						onClick={(e) => {
							e.stopPropagation();
							setZoomedImage(null);
						}}
					>
						<svg
							className="w-8 h-8"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
					<div
						role="dialog"
						aria-modal="true"
						className="relative max-w-4xl w-full max-h-full overflow-hidden flex items-center justify-center"
						onClick={(e) => e.stopPropagation()}
						onKeyDown={(e) => e.stopPropagation()}
					>
						<img
							src={zoomedImage}
							alt="Zoomed figure"
							className="max-w-full max-h-[90vh] object-contain shadow-2xl rounded-lg"
						/>
					</div>
				</button>
			)}
		</div>
	);
};

export default FigureInsight;

import { useEffect, useState } from "react";
import { API_URL } from "@/config";
import { usePaperCache } from "../../db/hooks";
import CopyButton from "../Common/CopyButton";
import MarkdownContent from "../Common/MarkdownContent";

interface FigureData {
	id: string;
	figure_id?: string; // Fallback
	image_url: string;
	explanation: string;
	caption?: string;
	page_number: number;
	page_num?: number; // Fallback
	label?: string;
}

interface FigureInsightProps {
	paperId?: string | null;
	onExplain?: (figureId: string) => void;
}

const FigureInsight: React.FC<FigureInsightProps> = ({
	paperId,
	onExplain,
}) => {
	const [figures, setFigures] = useState<FigureData[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [zoomedImage, setZoomedImage] = useState<string | null>(null);

	const { getCachedPaper } = usePaperCache();

	useEffect(() => {
		if (paperId && paperId !== "pending") {
			fetchFigures(paperId);
		} else {
			setFigures([]);
		}
	}, [paperId]);

	const fetchFigures = async (id: string) => {
		setLoading(true);
		setError(null);
		try {
			// 1. Try IndexedDB first (Fast & Support Transient papers)
			const cached = await getCachedPaper(id);
			if (cached?.layout_json) {
				try {
					const layout = JSON.parse(cached.layout_json);
					const allFigures: FigureData[] = [];
					if (Array.isArray(layout)) {
						layout.forEach((page: any, idx: number) => {
							if (page.figures && Array.isArray(page.figures)) {
								page.figures.forEach((fig: any, fIdx: number) => {
									allFigures.push({
										id: fig.id || `cached-${idx + 1}-${fIdx}`,
										image_url: fig.image_url,
										explanation: fig.explanation || "",
										caption: fig.caption || "",
										page_number: idx + 1,
										label: fig.label || "figure",
									});
								});
							}
						});
					}
					if (allFigures.length > 0) {
						console.log("[FigureInsight] Loaded from cache");
						setFigures(allFigures);
						setLoading(false);
						// We still want to background fetch to get explanations?
						// For transient guest mode, there won't be anything on the server anyway.
						// So we can return here.
						return;
					}
				} catch (e) {
					console.warn("[FigureInsight] Cache parse failed", e);
				}
			}

			// 2. Fallback to API
			const res = await fetch(`${API_URL}/api/papers/${id}/figures`);
			if (res.ok) {
				const data = await res.json();
				setFigures(data.figures || []);
			} else {
				// If 404, maybe no figures yet
				if (res.status !== 404) {
					setError("Failed to load figures");
				}
			}
		} catch (e) {
			setError("Error loading figures");
			console.error(e);
		} finally {
			setLoading(false);
		}
	};

	const handleExplain = async (figureId: string) => {
		if (onExplain) {
			onExplain(figureId);
		}
	};

	return (
		<div className="flex flex-col h-full bg-slate-50 relative">
			<div className="p-4 border-b border-slate-200 bg-white shadow-sm flex justify-between items-center sticky top-0 z-10">
				<h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
					Figures & Charts
				</h3>
				<button
					type="button"
					onClick={() => {
						if (paperId && paperId !== "pending") fetchFigures(paperId);
					}}
					className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-orange-600 transition-colors disabled:opacity-30"
					title="Reload"
					disabled={!paperId || paperId === "pending" || loading}
				>
					<svg
						className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
				</button>
			</div>

			<div className="flex-1 overflow-y-auto p-4 space-y-6">
				{(!paperId || paperId === "pending") && (
					<div className="text-center py-20 text-slate-400">
						<div className="bg-white w-16 h-16 rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-4 border border-slate-100">
							<div className="animate-spin rounded-full h-8 w-8 border-2 border-orange-100 border-t-orange-600"></div>
						</div>
						<p className="text-xs font-medium text-slate-500">
							Detecting Figures...
						</p>
						<p className="text-[10px] text-slate-400 mt-2 px-6">
							AI is scanning the paper for charts and tables.
						</p>
					</div>
				)}

				{loading && figures.length === 0 && paperId !== "pending" && (
					<div className="flex justify-center py-10">
						<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
					</div>
				)}

				{error && (
					<div className="text-xs text-red-500 text-center py-4 bg-red-50 rounded-lg border border-red-100">
						{error}
					</div>
				)}

				{!loading &&
					figures.length === 0 &&
					paperId &&
					paperId !== "pending" && (
						<div className="text-center py-12 px-6 bg-white rounded-2xl border border-slate-100 shadow-sm">
							<div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
								<svg
									className="w-8 h-8 text-slate-200"
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
							<h4 className="text-xs font-bold text-slate-600 mb-1">
								No figures identified
							</h4>
							<p className="text-[10px] text-slate-400 leading-relaxed">
								We couldn't find any distinct figures, tables, or complex charts
								in this paper.
							</p>
						</div>
					)}

				{figures.map((fig) => {
					const figId = fig.id || fig.figure_id;
					const pageNum = fig.page_number || fig.page_num;

					return (
						<div
							key={figId}
							className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden group hover:shadow-md transition-shadow"
						>
							{/* Image Container */}
							<button
								type="button"
								onClick={() => fig.image_url && setZoomedImage(fig.image_url)}
								onKeyDown={(e) => {
									if (e.key === "Enter" || e.key === " ") {
										if (fig.image_url) setZoomedImage(fig.image_url);
									}
								}}
								className="relative w-full bg-slate-100 aspect-video flex items-center justify-center overflow-hidden border-b border-slate-100 cursor-zoom-in group/img border-none p-0"
							>
								{fig.image_url ? (
									<>
										<img
											src={
												fig.image_url.startsWith("http")
													? fig.image_url
													: `${API_URL}${fig.image_url}`
											}
											alt={`Figure on page ${pageNum}`}
											className="max-w-full max-h-full object-contain transition-transform group-hover/img:scale-105"
											loading="lazy"
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
									</>
								) : (
									<span className="text-xs text-slate-400">Image missing</span>
								)}
								<div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm">
									P.{pageNum}
								</div>
								{fig.label && fig.label !== "image" && (
									<div className="absolute top-2 right-2 bg-orange-600/80 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm uppercase">
										{fig.label}
									</div>
								)}
							</button>

							{/* Content */}
							<div className="p-4">
								{fig.explanation ? (
									<div className="text-xs text-slate-600 leading-relaxed relative">
										<div className="flex justify-between items-center mb-1">
											<span className="font-bold text-orange-600 text-[10px] uppercase tracking-wider">
												Analysis
											</span>
											<CopyButton text={fig.explanation} size={12} />
										</div>
										<MarkdownContent className="prose prose-xs max-w-none text-xs text-slate-600 leading-relaxed">
											{fig.explanation}
										</MarkdownContent>
									</div>
								) : (
									<div className="flex flex-col items-center justify-center py-2">
										<button
											type="button"
											onClick={() => figId && handleExplain(figId)}
											className="flex items-center space-x-2 px-4 py-2 bg-orange-50 hover:bg-orange-100 text-orange-600 rounded-lg text-[11px] font-bold transition-colors group"
										>
											<svg
												className="w-3.5 h-3.5"
												fill="currentColor"
												viewBox="0 0 20 20"
											>
												<path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
												<path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
											</svg>
											<span>この図についてチャットで聞く</span>
										</button>
									</div>
								)}
							</div>
						</div>
					);
				})}
			</div>

			{/* Zoom Modal */}
			{zoomedImage && (
				<button
					type="button"
					className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4 md:p-8 transition-opacity duration-300 border-none w-full h-full text-left"
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
						className="relative max-w-4xl w-full max-h-full overflow-hidden flex items-center justify-center transition-transform duration-300 scale-100"
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

import { useLiveQuery } from "dexie-react-hooks";
import React, {
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { useTranslation } from "react-i18next";
import { createLogger } from "@/lib/logger";
import { db } from "../../db";
import { useIntersectionObserver } from "../../hooks/useIntersectionObserver";
import StampOverlay from "../Stamps/StampOverlay";
import type { Stamp } from "../Stamps/types";
import BoxOverlay from "./BoxOverlay";
import type { PageData, SelectedFigure } from "./types";

const log = createLogger("PDFPage");

// Interactive targets in click mode (matches inference-service TARGET_CLASSES)
const INTERACTIVE_TYPES = new Set([
	"table",
	"figure",
	"picture",
	"formula",
	"chart",
	"algorithm",
	"equation",
]);

interface PDFPageProps {
	page: PageData;
	scale?: number;
	onWordClick?: (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
		conf?: number,
	) => void;
	onTextSelect?: (
		text: string,
		coords: { page: number; x: number; y: number },
	) => void;
	// Stamp props
	stamps?: Stamp[];
	isStampMode?: boolean;
	onAddStamp?: (page: number, x: number, y: number) => void;
	onDeleteStamp?: (stampId: string) => void;
	// Area selection props
	isAreaMode?: boolean;
	onAreaSelect?: (coords: {
		page: number;
		x: number;
		y: number;
		width: number;
		height: number;
	}) => void;
	onAskAI?: (
		prompt: string,
		imageUrl?: string,
		coords?: any,
		originalText?: string,
		contextText?: string,
	) => void;
	onFigureSelect?: (figure: SelectedFigure) => void;
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
	// 検索関連props
	searchTerm?: string;
	currentSearchMatch?: { page: number; wordIndex: number } | null;
	evidenceHighlights?: Array<{
		x: number;
		y: number;
		width: number;
		height: number;
	}>;
	isLocal?: boolean;
	onPageVisible?: (pageNum: number) => void;
}

const PDFPage: React.FC<PDFPageProps> = ({
	page,
	onWordClick,
	onTextSelect,
	stamps = [],
	isStampMode = false,
	onAddStamp,
	onDeleteStamp,
	isAreaMode = false,
	onAreaSelect,
	onAskAI,
	onFigureSelect,
	jumpTarget,
	searchTerm,
	currentSearchMatch,
	evidenceHighlights = [],
	isLocal = false,
	onPageVisible,
}) => {
	const { t } = useTranslation();
	const { width, height, words, figures, image_url, page_num } = page;

	// Intersection Observer: only render overlays when page is near viewport
	const pageRef = useRef<HTMLElement>(null);
	const isVisible = useIntersectionObserver(pageRef);

	// ページがビューポートに入ったら親に通知（モード切替時のページ同期用）
	useEffect(() => {
		if (isVisible) {
			onPageVisible?.(page_num);
		}
	}, [isVisible, page_num, onPageVisible]);

	// Check for cached image in IndexedDB
	const cachedImage = useLiveQuery(async () => {
		if (!image_url) return undefined;
		return await db.images.get(image_url);
	}, [image_url]);

	const [displayUrl, setDisplayUrl] = useState(image_url);
	const [imageError, setImageError] = useState(false);

	useEffect(() => {
		if (cachedImage?.blob) {
			const blobUrl = URL.createObjectURL(cachedImage.blob);
			setDisplayUrl(blobUrl);
			setImageError(false);
			return () => {
				URL.revokeObjectURL(blobUrl);
			};
		} else {
			setDisplayUrl(image_url);
			setImageError(false);
		}
	}, [cachedImage, image_url]);

	// Text Selection State
	const [isDragging, setIsDragging] = React.useState(false);
	const [selectionStart, setSelectionStart] = React.useState<number | null>(
		null,
	);
	const [selectionEnd, setSelectionEnd] = React.useState<number | null>(null);
	const [selectionMenu, setSelectionMenu] = React.useState<{
		x: number;
		y: number;
		text: string;
		context: string;
		coords: any;
	} | null>(null);

	// useCallback でラップして参照を安定化。isDragging 変化時のみ再生成される。
	// isClickMode は親コンテナの data 属性で判断し、prop 依存を排除（再レンダー抑制）。
	const handleMouseUp = useCallback(() => {
		if (isStampMode || isAreaMode) return;
		// クリックモードかどうかを DOM の data 属性から判断する。
		// これにより isClickMode prop が不要になり、モード切り替え時の全ページ再レンダーを防ぐ。
		const pageEl = document.getElementById(`page-${page_num}`);
		if (!pageEl?.closest("[data-click-mode]")) return;

		if (isDragging && selectionStart !== null && selectionEnd !== null) {
			setIsDragging(false);

			if (selectionStart !== selectionEnd) {
				// Multi-word selection -> Show Menu
				const min = Math.min(selectionStart, selectionEnd);
				const max = Math.max(selectionStart, selectionEnd);
				const selectedWords = words.slice(min, max + 1);
				const text = selectedWords.map((w) => w.word).join(" ");
				const startCtx = Math.max(0, min - 10);
				const endCtx = Math.min(words.length, max + 10);
				const context = words
					.slice(startCtx, endCtx)
					.map((w) => w.word)
					.join(" ");

				const validWords = (selectedWords || []).filter(
					(w) => w?.bbox && w.bbox.length >= 4,
				);
				if (validWords.length === 0) {
					setSelectionStart(null);
					setSelectionEnd(null);
					return;
				}

				const x1 = Math.min(...validWords.map((w) => w.bbox[0]));
				const y1 = Math.min(...validWords.map((w) => w.bbox[1]));
				const x2 = Math.max(...validWords.map((w) => w.bbox[2]));
				const y2 = Math.max(...validWords.map((w) => w.bbox[3]));

				const pageWidth = width || 1;
				const pageHeight = height || 1;

				const centerPctX = ((x1 + x2) / 2 / pageWidth) * 100;
				const bottomPctY = (y2 / pageHeight) * 100;

				const centerX = (x1 + x2) / 2 / pageWidth;
				const centerY = (y1 + y2) / 2 / pageHeight;

				setSelectionMenu({
					x: centerPctX,
					y: bottomPctY,
					text,
					context,
					coords: { page: page_num, x: centerX, y: centerY },
				});
			} else {
				// Single click
				setSelectionStart(null);
				setSelectionEnd(null);
			}
		}
	}, [
		isStampMode,
		isAreaMode,
		isDragging,
		selectionStart,
		selectionEnd,
		words,
		width,
		height,
		page_num,
		onWordClick,
		onTextSelect,
	]);

	// isDragging が true の間だけ window に mouseup を登録する。
	// 依存配列を正しく設定することで毎レンダーのリスナー登録/解除を防止。
	React.useEffect(() => {
		if (!isDragging) return;
		window.addEventListener("mouseup", handleMouseUp);
		return () => window.removeEventListener("mouseup", handleMouseUp);
	}, [isDragging, handleMouseUp]);

	// Additional helper to clear selection on outside click
	React.useEffect(() => {
		const handleClickOutside = () => {
			if (selectionMenu) {
				setSelectionMenu(null);
				setSelectionStart(null);
				setSelectionEnd(null);
			}
		};

		if (selectionMenu) {
			document.addEventListener("mousedown", handleClickOutside);
		}
		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
		};
	}, [selectionMenu]);

	// Filter stamps for this page
	const pageStamps = useMemo(() => {
		return stamps.filter((s) => s.page_number === page_num || !s.page_number);
	}, [stamps, page_num]);

	const handleAddStamp = (x: number, y: number) => {
		if (onAddStamp) {
			onAddStamp(page_num, x, y);
		}
	};

	return (
		<section
			ref={pageRef}
			aria-label={`${t("viewer.page")} ${page.page_num}`}
			id={`page-${page.page_num}`}
			className="pdf-page-container relative mb-8 shadow-2xl rounded-xl overflow-hidden bg-white transition-all duration-300 border border-slate-200/50 mx-auto"
			style={{ width: "100%", maxWidth: "100%" }}
			onMouseUp={handleMouseUp}
		>
			{/* Header / Page Number */}
			<div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
				<span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
					{t("viewer.page")} {page.page_num}
				</span>
			</div>

			{/* Main Viewport Container */}
			<div
				className="relative w-full overflow-hidden pdf-page-viewport"
				style={{
					aspectRatio: width && height ? `${width}/${height}` : "auto",
					backgroundColor: "#fff",
				}}
			>
				{/* Page Image (Underlay) */}
				{!imageError && displayUrl ? (
					<img
						src={displayUrl}
						alt={`Page ${page.page_num}`}
						className="absolute inset-0 w-full h-full object-contain block select-none"
						loading="lazy"
						onError={() => {
							log.warn("load_image", "Image failed to load", {
								displayUrl,
								page_num,
							});
							setImageError(true);
						}}
						onLoad={() => setImageError(false)}
					/>
				) : (
					/* Fallback: Show message when image fails to load */
					<div className="absolute inset-0 bg-slate-50 flex flex-col items-center justify-center p-8 text-slate-500">
						<div className="text-4xl mb-4">📄</div>
						<p className="text-sm font-medium mb-2">
							{t("viewer.image_not_available", "画像を読み込めません")}
						</p>
						<p className="text-xs text-slate-400">
							{t(
								"viewer.text_mode_hint",
								"テキストモードでコンテンツを表示できます",
							)}
						</p>
					</div>
				)}

				{/* Figure/Table Overlays - only render when page is visible */}
				{isVisible && (
					<div className="absolute inset-0 w-full h-full z-50 pointer-events-none">
						{figures &&
							figures.length > 0 &&
							figures.map((fig, idx) => {
								if (!fig || !fig.bbox || fig.bbox.length < 4) return null;
								const [x1, y1, x2, y2] = fig.bbox;
								if (x1 === 0 && y1 === 0 && x2 === 0 && y2 === 0) return null;

								const label = (fig.label || "").toLowerCase();

								const isInteractiveType = INTERACTIVE_TYPES.has(label);

								// Production: skip non-interactive elements for clean UI (Req 3.4)
								// Development: show all elements with debug borders/confidence
								if (!isInteractiveType && !isLocal) return null;

								const pageWidth = width || 1;
								const pageHeight = height || 1;

								const style = {
									left: `${(x1 / pageWidth) * 100}%`,
									top: `${(y1 / pageHeight) * 100}%`,
									width: `${((x2 - x1) / pageWidth) * 100}%`,
									height: `${((y2 - y1) / pageHeight) * 100}%`,
								};

								/*
							log.debug("render_figure", "Rendering figure", {
								idx,
								label: fig.label,
								bbox: fig.bbox,
								page_num,
							});
							*/

								// group-data-[click-mode]/viewer バリアントで親コンテナの data 属性に連動。
								// isClickMode prop なしでモード変化を CSS で表現し、再レンダーを防止。
								// クリックモード時は pointer-events-auto にして bbox 全体のホバー検出を有効化。
								return (
									<div
										key={`fig-img-${idx}`}
										className={`absolute group pointer-events-none group-data-[click-mode]/viewer:pointer-events-auto group-data-[click-mode]/viewer:rounded-sm ${
											isLocal
												? "group-data-[click-mode]/viewer:border group-data-[click-mode]/viewer:border-orange-300/40"
												: ""
										}`}
										style={style}
									>
										{/* クリックモード時のみ表示するインタラクティブ要素。
									    クリックモードでは bbox 全体が pointer-events-auto になり group-hover で
									    Ask AI ボタンを表示できる。bbox 線は非表示。 */}
										<div className="hidden group-data-[click-mode]/viewer:block">
											{/* ラベルバッジ (isLocal=true のみ) */}
											{isLocal && fig.label && (
												<div className="absolute top-0 left-0 bg-black/70 text-white text-[10px] px-1 py-0.5 rounded-br z-[9999] pointer-events-none">
													{fig.label}
												</div>
											)}

											{/* Ask AI button: interactive elements only (Req 6.5) */}
											{isInteractiveType && (
												<div className="absolute top-0 right-0 translate-x-1/2 -translate-y-1/2 z-[9999] pointer-events-auto opacity-0 group-hover:opacity-100 transition-opacity duration-200">
													<button
														type="button"
														className="bg-orange-600 text-white w-5 h-5 rounded-full shadow shadow-orange-500/30 hover:bg-orange-500 hover:shadow-orange-600/40 transition-all flex items-center justify-center cursor-pointer hover:scale-110 active:scale-95"
														onClick={(e) => {
															e.stopPropagation();
															if (onFigureSelect) {
																onFigureSelect({
																	id: fig.id,
																	image_url: fig.image_url,
																	label: fig.label,
																	caption: fig.caption,
																	page_number: page_num,
																	conf: fig.conf,
																});
															}
														}}
														title={t("menu.ask_ai")}
													>
														<span className="text-[9px] leading-none">✨</span>
													</button>
												</div>
											)}
										</div>
									</div>
								);
							})}
					</div>
				)}

				{/* Stamp Overlay */}
				<StampOverlay
					stamps={pageStamps}
					isStampMode={isStampMode}
					onAddStamp={handleAddStamp}
					onDeleteStamp={onDeleteStamp}
				/>

				{/* Box Selection Overlay */}
				<BoxOverlay
					isActive={isAreaMode}
					onSelect={(rect) => {
						if (onAreaSelect) {
							onAreaSelect({
								page: page_num,
								x: rect.x,
								y: rect.y,
								width: rect.width,
								height: rect.height,
							});
						}
					}}
				/>

				{/* Evidence Highlights (static to reduce CPU/GPU load) */}
				{evidenceHighlights.map((highlight, idx) => (
					<div
						key={`evidence-${idx}`}
						className="absolute evidence-highlight-static z-30"
						style={{
							left: `${highlight.x * 100}%`,
							top: `${highlight.y * 100}%`,
							width: `${highlight.width * 100}%`,
							height: `${highlight.height * 100}%`,
						}}
					/>
				))}

				{/* Word Overlays - only render when page is visible */}
				{isVisible && (
					<div className="absolute inset-0 w-full h-full z-40 pointer-events-none">
						{words &&
							words.length > 0 &&
							words.map((w, idx) => {
								if (!w || !w.bbox || w.bbox.length < 4) return null;
								const [x1, y1, x2, y2] = w.bbox;
								const w_width = x2 - x1;
								const w_height = y2 - y1;

								const pageWidth = width || 1;
								const pageHeight = height || 1;

								const left = (x1 / pageWidth) * 100;
								const top = (y1 / pageHeight) * 100;
								const styleW = (w_width / pageWidth) * 100;
								const styleH = (w_height / pageHeight) * 100;

								const isSelected =
									selectionStart !== null &&
									selectionEnd !== null &&
									((idx >= selectionStart && idx <= selectionEnd) ||
										(idx >= selectionEnd && idx <= selectionStart));

								const centerX = (x1 + x2) / 2 / pageWidth;
								const centerY = (y1 + y2) / 2 / pageHeight;
								const cleanWord = (w.word || "").replace(
									/^[.,;!?(){}[\]"']+|[.,;!?(){}[\]"']+$/g,
									"",
								);
								const isPhraseTerm = !!jumpTarget?.term?.includes(" ");
								const isJumpHighlight =
									jumpTarget &&
									jumpTarget.page === page_num &&
									((jumpTarget.term
										?.toLowerCase()
										.includes(cleanWord.toLowerCase()) &&
										// フレーズ翻訳の場合: X許容範囲を広く取る（句全体をカバー）
										Math.abs(centerX - jumpTarget.x) <
											(isPhraseTerm ? 0.5 : 0.1) &&
										Math.abs(centerY - jumpTarget.y) < 0.05) ||
										(Math.abs(centerX - jumpTarget.x) < 0.005 &&
											Math.abs(centerY - jumpTarget.y) < 0.005));

								// 検索マッチングのハイライト
								const isSearchMatch =
									searchTerm &&
									searchTerm.length >= 2 &&
									w.word.toLowerCase().includes(searchTerm.toLowerCase());

								// 現在フォーカスされている検索マッチかどうか
								const isCurrentSearchMatch =
									currentSearchMatch &&
									currentSearchMatch.page === page_num &&
									currentSearchMatch.wordIndex === idx;

								return (
									<button
										key={`${idx}`}
										type="button"
										id={
											isCurrentSearchMatch ? "current-search-match" : undefined
										}
										className={`absolute rounded-sm group text-layer-word pointer-events-none group-data-[click-mode]/viewer:cursor-pointer group-data-[click-mode]/viewer:pointer-events-auto
										${!isStampMode && !isSelected && !isJumpHighlight && !isSearchMatch ? "" : ""}
										${isSelected ? "bg-orange-500/30 border border-orange-500/50" : ""}
										${isJumpHighlight ? "bg-yellow-400/60 z-20" : ""}
										${isSearchMatch && !isCurrentSearchMatch ? "bg-amber-300/50 border border-amber-400" : ""}
										${isCurrentSearchMatch ? "bg-orange-500/60 border-2 border-orange-600 shadow-[0_0_15px_rgba(249,115,22,0.6)] z-30 ring-2 ring-orange-400" : ""}`}
										style={{
											left: `${left}%`,
											top: `${top}%`,
											width: `${styleW}%`,
											height: `${styleH}%`,
											fontSize: `${styleH}cqh`,
											background:
												isSelected ||
												isJumpHighlight ||
												isSearchMatch ||
												isCurrentSearchMatch
													? undefined
													: "none",
											border:
												isSelected || isSearchMatch || isCurrentSearchMatch
													? undefined
													: "none",
											padding: 0,
											font: "inherit",
											color: "transparent",
											textAlign: "left",
											userSelect: "none", // Prevent accidental browser text selection interaction with overlay text content itself
										}}
										onMouseDown={(e) => {
											if (isStampMode || isAreaMode) return;
											if (!e.currentTarget.closest("[data-click-mode]")) return;
											e.preventDefault();
											e.stopPropagation();
											setIsDragging(true);
											setSelectionStart(idx);
											setSelectionEnd(idx);
											setSelectionMenu(null); // Hide menu on new select start
										}}
										onMouseEnter={() => {
											if (isDragging && selectionStart !== null) {
												setSelectionEnd(idx);
											}
										}}
										onClick={(e) => {
											e.stopPropagation(); // Stop propagation to document
											if (!isStampMode && !isAreaMode && onWordClick) {
												if (!e.currentTarget.closest("[data-click-mode]"))
													return;
												if (selectionStart === selectionEnd && !selectionMenu) {
													const start = Math.max(0, idx - 20);
													const end = Math.min(words.length, idx + 20);
													const context = words
														.slice(start, end)
														.map((w) => w.word)
														.join(" ");

													const wordCenterX = (x1 + x2) / 2 / pageWidth;
													const wordCenterY = (y1 + y2) / 2 / pageHeight;

													onWordClick(
														cleanWord,
														context,
														{
															page: page_num,
															x: wordCenterX,
															y: wordCenterY,
														},
														w.conf,
													);
												}
											}
										}}
										title={w.word}
									>
										{/* Text is hidden to prevent doubling effect with background image */}
									</button>
								);
							})}
					</div>
				)}

				{/* Note: Original figure click labels removed from z-20 as we now use z-30 images */}

				{/* Link Overlays */}
				<div className="absolute inset-0 w-full h-full z-20 pointer-events-none">
					{page.links &&
						page.links.length > 0 &&
						page.links.map((link, idx) => {
							if (!link || !link.bbox || link.bbox.length < 4) return null;
							const [x1, y1, x2, y2] = link.bbox;
							const l_width = x2 - x1;
							const l_height = y2 - y1;
							const pageWidth = width || 1;
							const pageHeight = height || 1;

							const left = (x1 / pageWidth) * 100;
							const top = (y1 / pageHeight) * 100;
							const styleW = (l_width / pageWidth) * 100;
							const styleH = (l_height / pageHeight) * 100;

							return (
								<button
									type="button"
									key={`link-${idx}`}
									className="absolute cursor-pointer pointer-events-auto border border-blue-400/0 hover:border-blue-400/50 hover:bg-blue-400/10 transition-all rounded-sm z-30"
									style={{
										left: `${left}%`,
										top: `${top}%`,
										width: `${styleW}%`,
										height: `${styleH}%`,
									}}
									onClick={(e) => {
										e.stopPropagation();
										if (onWordClick) {
											onWordClick(link.url);
										}
										window.open(link.url, "_blank", "noopener,noreferrer");
									}}
									title={link.url}
								/>
							);
						})}
				</div>

				{/* Selection Menu */}
				{selectionMenu && (
					<div
						role="toolbar"
						aria-label="Selection menu"
						className="absolute z-60 flex gap-1 bg-white border border-slate-200 text-slate-900 p-1.5 rounded-lg shadow-xl transform -translate-x-1/2 gpu-accelerated"
						style={{
							left: `${selectionMenu.x}%`,
							top: `${selectionMenu.y}%`,
							marginTop: "8px",
						}}
						onMouseDown={(e) => e.stopPropagation()} // Prevent closing on click
					>
						<button
							type="button"
							onClick={(e) => {
								e.stopPropagation();
								if (onWordClick)
									onWordClick(
										selectionMenu.text,
										selectionMenu.context,
										selectionMenu.coords,
									);
								setSelectionMenu(null);
								setSelectionStart(null);
								setSelectionEnd(null);
							}}
							className="px-4 py-2 hover:bg-orange-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-100"
						>
							<span>文A</span> {t("menu.translate")}
						</button>

						{onAskAI && (
							<button
								type="button"
								onClick={(e) => {
									e.stopPropagation();
									const prompt = `以下の文章を、文脈（${selectionMenu.context}）の中での役割をふまえつつ、わかりやすく解説してください。\n\n対象の文章: "${selectionMenu.text}"`;
									onAskAI(
										prompt,
										undefined,
										selectionMenu.coords,
										selectionMenu.text,
										selectionMenu.context,
									);
									setSelectionMenu(null);
									setSelectionStart(null);
									setSelectionEnd(null);
								}}
								className="px-4 py-2 hover:bg-orange-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-100"
							>
								<span>💡</span> {t("menu.explain")}
							</button>
						)}

						<button
							type="button"
							onClick={(e) => {
								e.stopPropagation();
								if (onTextSelect)
									onTextSelect(selectionMenu.text, selectionMenu.coords);
								setSelectionMenu(null);
								setSelectionStart(null);
								setSelectionEnd(null);
							}}
							className="px-4 py-2 hover:bg-orange-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors rounded-r-lg"
						>
							<span>📝</span> {t("menu.note")}
						</button>

						{/* Triangle arrow */}
						<div className="absolute left-1/2 top-0 w-2 h-2 bg-white border-l border-t border-slate-200 transform -translate-x-1/2 -translate-y-1/2 rotate-45"></div>
					</div>
				)}
			</div>

			{/* Modal part removed */}
		</section>
	);
};

export default React.memo(PDFPage);

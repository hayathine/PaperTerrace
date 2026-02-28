import { useLiveQuery } from "dexie-react-hooks";
import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { db } from "../../db";
import StampOverlay from "../Stamps/StampOverlay";
import type { Stamp } from "../Stamps/types";
import BoxOverlay from "./BoxOverlay";
import type { PageData } from "./types";

const getFigTypeLabel = (t: any, label: string): string => {
	const keyMap: Record<string, string> = {
		table: "pdf.table",
		figure: "pdf.figure",
		equation: "pdf.equation",
		image: "pdf.image",
	};
	const normalizedLabel = (label || "").toLowerCase();
	const key = keyMap[normalizedLabel] || "pdf.figure";
	return t(key);
};

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
	// Area selection props
	isAreaMode?: boolean;
	onAreaSelect?: (coords: {
		page: number;
		x: number;
		y: number;
		width: number;
		height: number;
	}) => void;
	onAskAI?: (prompt: string) => void;
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
	// 検索関連props
	searchTerm?: string;
	currentSearchMatch?: { page: number; wordIndex: number } | null;
	// Click mode (text mode) flag
	isClickMode?: boolean;
	evidenceHighlights?: Array<{
		x: number;
		y: number;
		width: number;
		height: number;
	}>;
}

const PDFPage: React.FC<PDFPageProps> = ({
	page,
	onWordClick,
	onTextSelect,
	stamps = [],
	isStampMode = false,
	onAddStamp,
	isAreaMode = false,
	onAreaSelect,
	onAskAI,
	jumpTarget,
	searchTerm,
	currentSearchMatch,
	isClickMode = false,
	evidenceHighlights = [],
}) => {
	const { t } = useTranslation();
	const { width, height, words, figures, image_url, page_num } = page;

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
		}
	}, [cachedImage, image_url]);

	// Debug: Log page data when component mounts or updates
	useEffect(() => {
		console.debug(`[PDFPage ${page_num}] Rendering with data:`, {
			width,
			height,
			words_count: words?.length || 0,
			figures_count: figures?.length || 0,
			image_url,
			sample_word: words?.[0],
			sample_figure: figures?.[0],
			isClickMode,
		});
	}, [page_num, width, height, words, figures, image_url, isClickMode]);

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

	const handleMouseUp = () => {
		if (isStampMode || isAreaMode || !isClickMode) return;

		if (isDragging && selectionStart !== null && selectionEnd !== null) {
			setIsDragging(false);

			if (selectionStart !== selectionEnd) {
				// Multi-word selection -> Show Menu
				const min = Math.min(selectionStart, selectionEnd);
				const max = Math.max(selectionStart, selectionEnd);
				const selectedWords = words.slice(min, max + 1);
				const text = selectedWords.map((w) => w.word).join(" ");
				// Context: grab a bit more surrounding text? For now just the selected text as context + some padding
				const startCtx = Math.max(0, min - 10);
				const endCtx = Math.min(words.length, max + 10);
				const context = words
					.slice(startCtx, endCtx)
					.map((w) => w.word)
					.join(" ");

				// Calculate bounding box of selection for anchor

				// Position menu near the end of selection or center? Center is better.
				// We need pixel coordinates for the menu relative to the page container
				// bbox is [x1, y1, x2, y2] in PDF coordinates (unscaled if width/height match PDF)
				// BUT the words bbox in PageData are likely consistent with width/height.
				// In the render, we use percentages.
				// We want the menu to be absolute positioned in the div.
				// x1, y1 etc are relative to page 'width' and 'height'.

				// Let's use % for position
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
	};

	React.useEffect(() => {
		if (isDragging) {
			window.addEventListener("mouseup", handleMouseUp);
			return () => window.removeEventListener("mouseup", handleMouseUp);
		}
	});

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
			aria-label={`${t("viewer.page")} ${page.page_num}`}
			id={`page-${page.page_num}`}
			className="relative mb-8 shadow-2xl rounded-xl overflow-hidden bg-white transition-all duration-300 border border-slate-200/50 mx-auto"
			style={{ maxWidth: "100%" }}
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
						className="w-full h-auto block select-none"
						loading="lazy"
						onError={() => {
							console.warn("PDFPage: Image failed to load:", displayUrl);
							setImageError(true);
						}}
						onLoad={() => setImageError(false)}
					/>
				) : (
					/* Fallback: Show message when image fails to load */
					<div className="w-full min-h-[600px] bg-slate-50 flex flex-col items-center justify-center p-8 text-slate-500">
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

				{/* Figure/Table Overlays (Overwrites text layer) */}
				<div className="absolute inset-0 w-full h-full z-30 pointer-events-none">
					{figures &&
						figures.length > 0 &&
						figures.map((fig, idx) => {
							if (!fig || !fig.bbox || fig.bbox.length < 4) return null;
							const [x1, y1, x2, y2] = fig.bbox;
							if (
								(x1 === 0 && y1 === 0 && x2 === 0 && y2 === 0) ||
								!fig.image_url
							)
								return null;

							// Filter out non-visual elements that shouldn't block text interaction
							const label = (fig.label || "").toLowerCase();
							if (
								[
									"text",
									"title",
									"list",
									"header",
									"footer",
									"reference",
									"caption",
									"section-header",
									"footnote",
								].includes(label)
							) {
								return null;
							}

							const pageWidth = width || 1;
							const pageHeight = height || 1;

							const style = {
								left: `${(x1 / pageWidth) * 100}%`,
								top: `${(y1 / pageHeight) * 100}%`,
								width: `${((x2 - x1) / pageWidth) * 100}%`,
								height: `${((y2 - y1) / pageHeight) * 100}%`,
							};

							/*
							console.log(`[PDFPage ${page_num}] Rendering figure ${idx}:`, {
								label: fig.label,
								bbox: fig.bbox,
								style,
								isClickMode,
							});
							*/

							return (
								<div
									key={`fig-img-${idx}`}
									className={`absolute bg-white shadow-sm group ${
										isClickMode ? "pointer-events-auto" : "pointer-events-none"
									}`}
									style={style}
								>
									<img
										src={fig.image_url}
										className="w-full h-full object-fill"
										alt={fig.label}
									/>
									{isClickMode && (
										<>
											{/* Hover overlay for visual feedback */}
											<div className="absolute inset-0 bg-indigo-500/0 hover:bg-indigo-500/10 transition-colors border-2 border-transparent hover:border-indigo-400 rounded-sm pointer-events-none" />

											{/* Ask AI button shown on hover */}
											<div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity z-50">
												<button
													type="button"
													className="bg-indigo-600 text-white text-xs px-3 py-1.5 rounded-md shadow shadow-indigo-500/30 hover:bg-indigo-700 hover:shadow-indigo-600/40 transition-all font-medium flex items-center gap-1.5 cursor-pointer transform hover:scale-105 active:scale-95"
													onClick={(e) => {
														e.stopPropagation();
														if (onAskAI) {
															const typeName = getFigTypeLabel(
																t,
																fig.label || "figure",
															);
															// Jump directly to explanation
															onAskAI(
																t("chat.explain_fig", { type: typeName }),
															);
														}
													}}
													title={t("menu.ask_ai")}
												>
													<span className="text-xs">✨</span>
													{t("menu.ask_ai")}
												</button>
											</div>

											{/* Transparent overlay to grab clicks on the rest of the image to prevent text selection underneath */}
											<button
												type="button"
												aria-label="Selection overlay"
												className="absolute inset-0 w-full h-full z-40 bg-transparent"
												onClick={(e) => e.stopPropagation()}
											/>
										</>
									)}
								</div>
							);
						})}
				</div>

				{/* Stamp Overlay */}
				<StampOverlay
					stamps={pageStamps}
					isStampMode={isStampMode}
					onAddStamp={handleAddStamp}
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

				{/* Evidence Highlights */}
				{evidenceHighlights.map((highlight, idx) => (
					<div
						key={`evidence-${idx}`}
						className="absolute bg-emerald-400/30 border-2 border-emerald-500/50 rounded-sm z-30 pointer-events-none animate-[pulse_2s_infinite]"
						style={{
							left: `${highlight.x * 100}%`,
							top: `${highlight.y * 100}%`,
							width: `${highlight.width * 100}%`,
							height: `${highlight.height * 100}%`,
						}}
					/>
				))}

				{/* Word Overlays */}
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
							const isJumpHighlight =
								jumpTarget &&
								jumpTarget.page === page_num &&
								((jumpTarget.term &&
									(cleanWord
										.toLowerCase()
										.includes(jumpTarget.term.toLowerCase()) ||
										jumpTarget.term
											.toLowerCase()
											.includes(cleanWord.toLowerCase())) &&
									Math.abs(centerX - jumpTarget.x) < 0.1 &&
									Math.abs(centerY - jumpTarget.y) < 0.05) ||
									(Math.abs(centerX - jumpTarget.x) < 0.005 &&
										Math.abs(centerY - jumpTarget.y) < 0.005));

							// 検索マッチのハイライト
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
									id={isCurrentSearchMatch ? "current-search-match" : undefined}
									className={`absolute rounded-sm group text-layer-word ${!isStampMode && isClickMode ? "cursor-pointer pointer-events-auto" : "pointer-events-none"} 
                                    ${!isStampMode && !isSelected && !isJumpHighlight && !isSearchMatch ? "hover:bg-yellow-300/30" : ""} 
                                    ${isSelected ? "bg-indigo-500/30 border border-indigo-500/50" : ""}
                                    ${isJumpHighlight ? "bg-yellow-400/60 z-20" : ""}
                                    ${isSearchMatch && !isCurrentSearchMatch ? "bg-amber-300/50 border border-amber-400" : ""}
                                    ${isCurrentSearchMatch ? "bg-orange-500/60 border-2 border-orange-600 shadow-[0_0_15px_rgba(249,115,22,0.6)] z-30 ring-2 ring-orange-400" : ""}`}
									style={{
										left: `${left}%`,
										top: `${top}%`,
										width: `${styleW}%`,
										height: `${styleH}%`,
										fontSize: `${styleH}cqh`,
										background: "none",
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
										if (isStampMode || isAreaMode || !isClickMode) return;
										e.preventDefault();
										e.stopPropagation();
										setIsDragging(true);
										setSelectionStart(idx);
										setSelectionEnd(idx);
										setSelectionMenu(null); // Hide menu on new select start
									}}
									onMouseEnter={() => {
										if (isClickMode && isDragging && selectionStart !== null) {
											setSelectionEnd(idx);
										}
									}}
									onClick={(e) => {
										e.stopPropagation(); // Stop propagation to document
										if (
											!isStampMode &&
											!isAreaMode &&
											isClickMode &&
											onWordClick
										) {
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
						className="absolute z-60 flex gap-1 bg-gray-900 text-white p-1.5 rounded-lg shadow-xl transform -translate-x-1/2"
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
							className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-700"
						>
							<span>文A</span> {t("menu.translate")}
						</button>

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
							className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors"
						>
							<span>📝</span> {t("menu.note")}
						</button>

						{onAskAI && (
							<button
								type="button"
								onClick={(e) => {
									e.stopPropagation();
									const prompt = `以下の文章をわかりやすく解説してください。\n\n"${selectionMenu.text}"`;
									onAskAI(prompt);
									setSelectionMenu(null);
									setSelectionStart(null);
									setSelectionEnd(null);
								}}
								className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-l border-slate-700 rounded-r-lg"
							>
								<span>💡</span> {t("menu.explain")}
							</button>
						)}

						{/* Triangle arrow */}
						<div className="absolute left-1/2 top-0 w-2 h-2 bg-gray-900 transform -translate-x-1/2 -translate-y-1/2 rotate-45"></div>
					</div>
				)}
			</div>

			{/* Modal part removed */}
		</section>
	);
};

export default React.memo(PDFPage);

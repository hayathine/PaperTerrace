import React from "react";
import { useTranslation } from "react-i18next";
import type { PageWithLines } from "./types";

interface TextModePageProps {
	page: PageWithLines;
	onWordClick?: (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
	) => void;
	onTextSelect?: (
		text: string,
		coords: { page: number; x: number; y: number },
	) => void;
	onAskAI?: (prompt: string) => void;
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
	searchTerm?: string;
	currentSearchMatch?: { page: number; wordIndex: number } | null;
}

const TextModePage: React.FC<TextModePageProps> = ({
	page,
	onWordClick,
	onTextSelect,
	onAskAI,
	jumpTarget,
	searchTerm,
	currentSearchMatch,
}) => {
	const { t } = useTranslation();
	const [imageError, setImageError] = React.useState(false);
	const [selectionMenu, setSelectionMenu] = React.useState<{
		x: number;
		y: number;
		text: string;
		coords: any;
	} | null>(null);
	React.useEffect(() => {
		const handleDocumentMouseUp = () => {
			// Selection detection can be tricky, small delay ensures selection state is updated
			setTimeout(() => {
				const selection = window.getSelection();
				const selectionText = selection?.toString().trim();
				const container = document.getElementById(`text-page-${page.page_num}`);

				if (
					selection &&
					selection.rangeCount > 0 &&
					selectionText &&
					selectionText.length > 0 &&
					container
				) {
					const range = selection.getRangeAt(0);

					// Only show menu for the page where the selection starts
					if (
						!container.contains(range.startContainer) &&
						range.startContainer !== container
					) {
						return;
					}

					const rect = container.getBoundingClientRect();
					const rangeRect = range.getBoundingClientRect();

					// Ensure we have a valid bounding box
					if (rangeRect.width === 0) return;

					const pageWidth = rect.width || 1;
					const pageHeight = rect.height || 1;

					const menuX =
						(((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth) *
						100;
					const menuY = ((rangeRect.bottom - rect.top) / pageHeight) * 100;

					const centerX =
						((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth;
					const centerY =
						((rangeRect.top + rangeRect.bottom) / 2 - rect.top) / pageHeight;

					setSelectionMenu({
						x: menuX,
						y: menuY,
						text: selectionText,
						coords: { page: page.page_num, x: centerX, y: centerY },
					});
				} else {
					// If there is no selection, but we currently have a menu, we shouldn't necessarily clear it here
					// because mousedown handles outside clicks. But if selection is empty natively, clear it.
					setSelectionMenu(null);
				}
			}, 10);
		};

		document.addEventListener("mouseup", handleDocumentMouseUp);
		return () => document.removeEventListener("mouseup", handleDocumentMouseUp);
	}, [page.page_num]);

	React.useEffect(() => {
		const handleClickOutside = (e: MouseEvent) => {
			if ((e.target as HTMLElement).closest(".selection-menu")) return;
			setSelectionMenu(null);
		};
		if (selectionMenu)
			document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, [selectionMenu]);

	return (
		<div
			id={`text-page-${page.page_num}`}
			className="relative shadow-sm bg-white border border-slate-200 group mx-auto"
			style={{
				maxWidth: "100%",
				userSelect: "none",
			}}
		>
			{/* Header */}
			<div className="bg-slate-50 border-b border-slate-200 px-4 py-1.5 flex justify-between items-center select-none">
				<span className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">
					Page {page.page_num}
				</span>
			</div>

			{/* Content Container */}
			<div
				className="relative w-full overflow-hidden min-h-[600px] bg-white pdf-page-viewport"
				style={{
					aspectRatio:
						page.width && page.height ? `${page.width}/${page.height}` : "auto",
				}}
			>
				{!imageError ? (
					<>
						{/* PDF Image (Base Layer) */}
						<img
							src={page.image_url}
							alt={`Page ${page.page_num}`}
							className="w-full h-auto block select-none pointer-events-none"
							loading="lazy"
							onError={() => {
								console.warn("Image failed to load:", page.image_url);
								setImageError(true);
							}}
							onLoad={() => {
								setImageError(false);
							}}
						/>

						{/* Transparent Text Layer (Overlay Layer) */}
						<div
							className="absolute inset-0 z-10 w-full h-full cursor-text selection:bg-indigo-600/30"
							style={{ userSelect: "text" }}
						>
							{page.lines?.map((line, lIdx) => {
								const [lx1, ly1, lx2, ly2] = line.bbox;
								const pWidth = page.width || 1;
								const pHeight = page.height || 1;
								const styleH = ((ly2 - ly1) / pHeight) * 100;
								const styleW = ((lx2 - lx1) / pWidth) * 100;
								const top = (ly1 / pHeight) * 100;
								const left = (lx1 / pWidth) * 100;

								return (
									<div
										key={`line-${lIdx}`}
										className="absolute text-transparent text-layer-line whitespace-pre"
										style={{
											top: `${top}%`,
											left: `${left}%`,
											width: `${styleW}%`,
											height: `${styleH}%`,
											fontSize: `${styleH * 0.85}cqh`,
											lineHeight: 1,
											pointerEvents: "auto",
											display: "flex",
											alignItems: "flex-end",
										}}
									>
										{line.words.map((w, wIdx) => {
											const globalWordIndex = page.words?.indexOf(w) ?? -1;

											const isJumpHighlight =
												jumpTarget &&
												jumpTarget.page === page.page_num &&
												jumpTarget.term &&
												w.word
													.toLowerCase()
													.includes(jumpTarget.term.toLowerCase());

											const isSearchMatch =
												searchTerm &&
												searchTerm.length >= 2 &&
												w.word.toLowerCase().includes(searchTerm.toLowerCase());

											const isCurrentSearchMatch =
												currentSearchMatch &&
												currentSearchMatch.page === page.page_num &&
												currentSearchMatch.wordIndex === globalWordIndex;

											return (
												<span
													key={wIdx}
													id={
														isCurrentSearchMatch
															? "current-search-match"
															: undefined
													}
													className={`
                            ${isJumpHighlight ? "bg-yellow-400/40 border-b border-yellow-600 z-20" : ""}
                            ${isSearchMatch && !isCurrentSearchMatch ? "bg-amber-300/50 rounded" : ""}
                            ${isCurrentSearchMatch ? "bg-orange-500/60 rounded ring-2 ring-orange-400 z-30" : ""}
                          `}
													style={{
														marginRight:
															wIdx < line.words.length - 1 ? "0.25em" : "0",
													}}
												>
													{w.word}
												</span>
											);
										})}
									</div>
								);
							})}
						</div>
					</>
				) : (
					/* Fallback: Text-only display when image fails to load */
					<div className="p-8 bg-gray-50 min-h-[600px]">
						<div className="prose max-w-none">
							<h3 className="text-lg font-semibold mb-4 text-gray-700">
								Page {page.page_num} - Text Content
							</h3>
							<div className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
								{page.lines.map((line, lIdx) => (
									<div key={lIdx} className="mb-2">
										{line.words.map((w, wIdx) => {
											const isJumpHighlight =
												jumpTarget &&
												jumpTarget.page === page.page_num &&
												jumpTarget.term &&
												w.word
													.toLowerCase()
													.includes(jumpTarget.term.toLowerCase());

											const isSearchMatch =
												searchTerm &&
												searchTerm.length >= 2 &&
												w.word.toLowerCase().includes(searchTerm.toLowerCase());

											return (
												<button
													key={wIdx}
													type="button"
													className={`${isJumpHighlight ? "bg-yellow-400/60 px-1 rounded" : ""} ${isSearchMatch ? "bg-amber-300/60 px-1 rounded" : ""} text-left`}
													onClick={() => {
														if (onWordClick) {
															onWordClick(w.word, undefined, {
																page: page.page_num,
																x: 0.5,
																y: 0.5,
															});
														}
													}}
													style={{
														cursor: "pointer",
														background: "none",
														border: "none",
														padding: 0,
														font: "inherit",
														color: "inherit",
													}}
												>
													{w.word}{" "}
												</button>
											);
										})}
									</div>
								))}
							</div>
						</div>
					</div>
				)}
			</div>

			{/* Selection Menu */}
			{selectionMenu && (
				<div
					role="toolbar"
					aria-label="Selection menu"
					className="selection-menu absolute z-50 flex gap-1 bg-gray-900 text-white p-1.5 rounded-lg shadow-xl overflow-hidden transform -translate-x-1/2"
					style={{
						left: `${selectionMenu.x}%`,
						top: `${selectionMenu.y}%`,
						marginTop: "8px",
					}}
					onMouseDown={(e) => e.stopPropagation()}
				>
					<button
						type="button"
						onClick={(e) => {
							e.stopPropagation();
							if (onWordClick)
								onWordClick(
									selectionMenu.text,
									undefined,
									selectionMenu.coords,
								);
							setSelectionMenu(null);
						}}
						className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-700"
					>
						<span>文A</span> {t("menu.translate", "Translate")}
					</button>

					<button
						type="button"
						onClick={(e) => {
							e.stopPropagation();
							if (onTextSelect)
								onTextSelect(selectionMenu.text, selectionMenu.coords);
							setSelectionMenu(null);
						}}
						className={`px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors ${onAskAI ? "border-r border-slate-700" : ""}`}
					>
						<span>📝</span> {t("menu.note", "Note")}
					</button>

					{onAskAI && (
						<button
							type="button"
							onClick={(e) => {
								e.stopPropagation();
								const prompt = `以下の文章をわかりやすく解説してください。\n\n"${selectionMenu.text}"`;
								onAskAI(prompt);
								setSelectionMenu(null);
							}}
							className="px-4 py-2 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors rounded-r-lg"
						>
							<span>💡</span> {t("menu.explain", "Explain")}
						</button>
					)}

					{/* Triangle arrow */}
					<div className="absolute left-1/2 top-0 w-2 h-2 bg-gray-900 transform -translate-x-1/2 -translate-y-1/2 rotate-45 pointer-events-none"></div>
				</div>
			)}
		</div>
	);
};

export default React.memo(TextModePage);

import React, {
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import type { Components } from "react-markdown";
import { API_URL } from "../../config";
import { useBookmarks } from "../../db/hooks";
import { useIntersectionObserver } from "../../hooks/useIntersectionObserver";
import { useTextSelection } from "../../hooks/useTextSelection";
import MarkdownContent from "../Common/MarkdownContent";
import {
	extractHeadingText,
	findFigureByBbox,
	highlightText,
	KNOWN_SECTIONS,
	parseBboxFromSrc,
} from "./textModeUtils";
import type { PageWithLines } from "./types";

/** 一度でも viewport に入ったら true のままにする（スクロール高さ変化によるジャンプ防止） */
function useVisibleOnce(
	ref: React.RefObject<Element | null>,
	options?: IntersectionObserverInit,
): boolean {
	const isIntersecting = useIntersectionObserver(ref, options);
	const hasBeenVisible = useRef(false);
	if (isIntersecting) hasBeenVisible.current = true;
	return hasBeenVisible.current;
}

interface TextModePageProps {
	page: PageWithLines;
	paperId?: string | null;
	paperTitle?: string;
	onWordClick?: (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
	) => void;
	onTextSelect?: (
		text: string,
		coords: { page: number; x: number; y: number },
	) => void;
	onAskAI?: (
		prompt: string,
		imageUrl?: string,
		coords?: any,
		originalText?: string,
		contextText?: string,
	) => void;
	searchTerm?: string;
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
	onPageVisible?: (pageNum: number) => void;
}

const TextModePage: React.FC<TextModePageProps> = ({
	page,
	paperId,
	paperTitle,
	onWordClick,
	onTextSelect,
	onAskAI,
	searchTerm,
	jumpTarget,
	onPageVisible,
}) => {
	const { t } = useTranslation();
	const { addBookmark, getPageBookmarks } = useBookmarks();
	const [isBookmarked, setIsBookmarked] = useState(false);
	const [bookmarkAdding, setBookmarkAdding] = useState(false);

	useEffect(() => {
		if (!paperId) return;
		getPageBookmarks(paperId, page.page_num).then(setIsBookmarked);
	}, [paperId, page.page_num, getPageBookmarks]);

	const handleBookmark = useCallback(async () => {
		if (!paperId || bookmarkAdding) return;
		setBookmarkAdding(true);
		const added = await addBookmark(
			paperId,
			paperTitle || "Untitled",
			page.page_num,
		);
		setIsBookmarked(added ?? false);
		setBookmarkAdding(false);
	}, [paperId, paperTitle, page.page_num, addBookmark, bookmarkAdding]);

	// Intersection Observer: delay heavy Markdown rendering until page is near viewport
	const containerRef = useRef<HTMLDivElement>(null);
	const isVisible = useVisibleOnce(containerRef, {
		rootMargin: "400px",
	});

	// ページがビューポートに入ったら親に通知（モード切替時のページ同期用）
	const isCurrentlyVisible = useIntersectionObserver(containerRef, {
		threshold: 0.1,
	});
	useEffect(() => {
		if (isCurrentlyVisible) {
			onPageVisible?.(page.page_num);
		}
	}, [isCurrentlyVisible, page.page_num, onPageVisible]);

	const { selectionMenu, clearSelectionMenu } = useTextSelection(page.page_num);
	const [zoomedImage, setZoomedImage] = useState<string | null>(null);

	// ⚠️ テキストモードでは「単語クリック→翻訳」は使わない。
	// 翻訳は必ずテキスト選択後の選択メニュー（Translate ボタン）経由のみ。
	// handleWordClick を article の onClick に戻さないこと。何度も同じ間違いが起きている。

	// --- コンテンツ: content が空なら lines フォールバック ---
	const processedMarkdown = useMemo(() => {
		let content = "";
		if (page.content && page.content.trim().length > 0) {
			content = page.content;
		} else if (page.lines && page.lines.length > 0) {
			content = page.lines
				.map((line) => line.words.map((w) => w.word).join(" "))
				.join("\n");
		}
		if (!content) return "";

		// 旧形式 ![label]([x, y, x, y]) → 新形式 ![label](<x,y,x,y>) に正規化する。
		// URLにスペースを含む旧キャッシュデータはMarkdownパーサーが画像として認識できないため。
		content = content.replace(
			/!\[([^\]]*)\]\(\[?([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)\]?\)/g,
			(_, label, x1, y1, x2, y2) => `![${label}](<${x1},${y1},${x2},${y2}>)`,
		);

		// フォールバック: content にマーカーがない figure を Y 座標で段落間に挿入する。
		// 旧キャッシュ論文（マーカー未生成）や遅延レイアウト解析で追加された figure に対応。
		if (Array.isArray(page.figures) && page.figures.length > 0) {
			// content 内に既に存在する bbox を収集
			const existingBboxes: number[][] = [];
			const markerRe = /!\[[^\]]*\]\(<([\d.]+),([\d.]+),([\d.]+),([\d.]+)>\)/g;
			let m: RegExpExecArray | null;
			// biome-ignore lint/suspicious/noAssignInExpressions: iteration idiom
			while ((m = markerRe.exec(content)) !== null) {
				existingBboxes.push([
					Number.parseFloat(m[1]),
					Number.parseFloat(m[2]),
					Number.parseFloat(m[3]),
					Number.parseFloat(m[4]),
				]);
			}

			const tol = 20;
			const unmatched = page.figures.filter(
				(fig) =>
					!existingBboxes.some(
						(eb) =>
							Math.abs(eb[0] - fig.bbox[0]) < tol &&
							Math.abs(eb[1] - fig.bbox[1]) < tol &&
							Math.abs(eb[2] - fig.bbox[2]) < tol &&
							Math.abs(eb[3] - fig.bbox[3]) < tol,
					),
			);

			if (unmatched.length > 0) {
				const pageHeight = page.height || 1;
				const paragraphs = content.split("\n\n");
				const refs = unmatched
					.map((fig) => ({
						y: fig.bbox[1],
						ref: `![${fig.label || "figure"}](<${fig.bbox[0]},${fig.bbox[1]},${fig.bbox[2]},${fig.bbox[3]}>)`,
					}))
					.sort((a, b) => a.y - b.y);

				let offset = 0;
				for (const { y, ref } of refs) {
					const insertIdx = Math.min(
						Math.floor((y / pageHeight) * paragraphs.length) + offset,
						paragraphs.length,
					);
					paragraphs.splice(insertIdx, 0, ref);
					offset += 1;
				}
				content = paragraphs.join("\n\n");
			}
		}

		return content;
	}, [page.content, page.lines, page.figures, page.height]);

	// --- react-markdown の components カスタマイズ ---
	const mdComponents: Components = useMemo(() => {
		const comps: Components = {};

		// Figure画像: ![alt]([x1,y1,x2,y2]) → 実画像URLにマッピング
		comps.img = ({ src, alt, ...rest }) => {
			if (src) {
				const bbox = parseBboxFromSrc(src);
				if (bbox) {
					const figure = findFigureByBbox(page.figures, bbox);
					if (figure?.image_url) {
						// /static/... の相対パスの場合は API_URL プレフィックスを付与
						const imgSrc = figure.image_url.startsWith("http")
							? figure.image_url
							: `${API_URL}${figure.image_url}`;

						// bbox と page.width から元のサイズ比率を計算
						const figWidthPercent = page.width
							? ((figure.bbox[2] - figure.bbox[0]) / page.width) * 100
							: null;

						return (
							<img
								src={imgSrc}
								alt={alt || figure.label || "Figure"}
								onClick={() => setZoomedImage(imgSrc)}
								className="mx-auto my-4 rounded shadow-sm border border-slate-200 object-contain cursor-zoom-in hover:brightness-[0.98] transition-all"
								style={
									figWidthPercent
										? { width: `${figWidthPercent}%`, height: "auto" }
										: { width: "50%", height: "auto" }
								}
								loading="lazy"
								{...rest}
							/>
						);
					}
					// bbox はあるが figure にマッチしない場合は非表示（レイアウト崩れを防ぐ）
					return null;
				}
			}
			// 通常の画像
			return (
				<img
					src={src}
					alt={alt}
					onClick={() => {
						if (src) setZoomedImage(src);
					}}
					className="mx-auto my-4 rounded shadow-sm object-contain cursor-zoom-in hover:brightness-[0.98] transition-all"
					style={{ width: "50%", height: "auto" }}
					loading="lazy"
					{...rest}
				/>
			);
		};

		// Markdown テーブル: スクロール可能なラッパーでレスポンシブ表示する
		comps.table = ({ children, ...rest }) => (
			<div className="overflow-x-auto my-4 rounded border border-slate-200">
				<table className="min-w-full text-sm border-collapse" {...rest}>
					{children}
				</table>
			</div>
		);
		comps.thead = ({ children, ...rest }) => (
			<thead className="bg-slate-50 text-slate-700 font-semibold" {...rest}>
				{children}
			</thead>
		);
		comps.tbody = ({ children, ...rest }) => (
			<tbody className="divide-y divide-slate-100" {...rest}>
				{children}
			</tbody>
		);
		comps.tr = ({ children, ...rest }) => (
			<tr className="hover:bg-slate-50 transition-colors" {...rest}>
				{children}
			</tr>
		);
		comps.th = ({ children, ...rest }) => (
			<th
				className="px-3 py-2 text-left border-b border-slate-200 whitespace-nowrap"
				{...rest}
			>
				{searchTerm && searchTerm.length >= 2
					? highlightText(children, searchTerm)
					: children}
			</th>
		);
		comps.td = ({ children, ...rest }) => (
			<td className="px-3 py-2 align-top" {...rest}>
				{searchTerm && searchTerm.length >= 2
					? highlightText(children, searchTerm)
					: children}
			</td>
		);

		// Markdown リンク: 新規タブで開く（同タブ遷移防止）
		comps.a = ({ href, children }) => (
			<a
				href={href}
				target="_blank"
				rel="noopener noreferrer"
				className="text-blue-600 hover:text-blue-800 underline"
				onClick={(e) => e.stopPropagation()}
			>
				{children}
			</a>
		);

		// 検索ハイライト: テキスト要素をラップ（td/th はテーブルコンポーネント内で処理済み）
		if (searchTerm && searchTerm.length >= 2) {
			comps.p = ({ children, ...rest }) => (
				<p {...rest}>{highlightText(children, searchTerm)}</p>
			);
			comps.li = ({ children, ...rest }) => (
				<li {...rest}>{highlightText(children, searchTerm)}</li>
			);
		}

		// 見出し H1 — 論文タイトル（常時カスタムスタイル、検索ハイライトも内部で処理）
		comps.h1 = ({ children, ...rest }) => {
			const content =
				searchTerm && searchTerm.length >= 2
					? highlightText(children, searchTerm)
					: children;
			return (
				<h1
					className="text-2xl font-bold text-slate-800 leading-snug tracking-tight mt-2 mb-6 pb-4 border-b-2 border-slate-300 break-words"
					{...rest}
				>
					{content}
				</h1>
			);
		};

		// 見出し H2 — セクション（Abstract, Introduction など）
		comps.h2 = ({ children, ...rest }) => {
			const headingText = extractHeadingText(children).toLowerCase();
			const isKnown = KNOWN_SECTIONS.some((s) => headingText.includes(s));
			const content =
				searchTerm && searchTerm.length >= 2
					? highlightText(children, searchTerm)
					: children;
			return (
				<h2
					className={`text-base font-bold mt-8 mb-3 pb-1 border-b break-words ${
						isKnown
							? "text-orange-700 border-orange-200"
							: "text-slate-700 border-slate-200"
					}`}
					{...rest}
				>
					{content}
				</h2>
			);
		};

		// 見出し H3 — サブセクション
		comps.h3 = ({ children, ...rest }) => {
			const content =
				searchTerm && searchTerm.length >= 2
					? highlightText(children, searchTerm)
					: children;
			return (
				<h3
					className="text-sm font-bold text-slate-700 mt-6 mb-2 pl-2 border-l-2 border-slate-300 break-words"
					{...rest}
				>
					{content}
				</h3>
			);
		};

		// 見出し H4 — サブサブセクション
		comps.h4 = ({ children, ...rest }) => {
			const content =
				searchTerm && searchTerm.length >= 2
					? highlightText(children, searchTerm)
					: children;
			return (
				<h4
					className="text-sm font-semibold text-slate-600 mt-4 mb-1.5 italic break-words"
					{...rest}
				>
					{content}
				</h4>
			);
		};

		return comps;
	}, [page.figures, searchTerm]);

	return (
		<div
			ref={containerRef}
			id={`text-page-${page.page_num}`}
			className="text-page-container relative shadow-sm bg-white border border-slate-200 group mx-auto w-full max-w-full rounded-xl overflow-hidden"
			style={{ userSelect: "auto", maxWidth: "100%" }}
		>
			{/* Header */}
			<div className="bg-slate-50 border-b border-slate-200 px-4 py-1.5 flex justify-between items-center select-none">
				<span className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">
					Page {page.page_num}
				</span>
				{paperId && (
					<button
						type="button"
						onClick={handleBookmark}
						disabled={bookmarkAdding}
						title={isBookmarked ? "しおりを外す" : "このページをしおりに追加"}
						className={`p-1.5 rounded transition-colors ${
							isBookmarked
								? "text-orange-500 hover:text-orange-700"
								: "text-slate-400 hover:text-orange-400"
						}`}
					>
						<svg
							className="w-5 h-5"
							fill={isBookmarked ? "currentColor" : "none"}
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
							/>
						</svg>
					</button>
				)}
			</div>

			{/* Jump target indicator: Y座標にパルスアニメーションで場所を示す */}
			{jumpTarget && (
				<div
					className="pointer-events-none absolute left-0 right-0 z-20"
					style={{ top: `${jumpTarget.y * 100}%` }}
				>
					<div className="h-0.5 bg-orange-400 animate-pulse opacity-80" />
					<div className="absolute left-2 -top-3 bg-orange-400 text-white text-[9px] px-1.5 py-0.5 rounded font-bold animate-pulse">
						↓
					</div>
				</div>
			)}

			{/* Markdown Content - lazy render when off-screen to save React/browser work */}
			{isVisible ? (
				<article className="px-3 py-4 sm:px-6 sm:py-5 md:px-10 md:py-8 selection:bg-orange-600/30 overflow-x-hidden">
					{processedMarkdown ? (
						<MarkdownContent
							className="prose prose-slate max-w-none prose-p:my-3 prose-p:leading-7 prose-li:my-1 prose-li:leading-7 prose-img:mx-auto prose-img:max-w-full [&_.katex]:text-base [&_.katex]:font-normal [&_.katex-display]:my-4 [&_.math-display]:block [&_.katex-display]:overflow-x-auto [&_.katex-display]:max-w-full prose-pre:overflow-x-auto prose-pre:max-w-full break-words"
							components={mdComponents}
						>
							{processedMarkdown}
						</MarkdownContent>
					) : (
						<p className="text-slate-400 italic text-sm">
							No content available for this page.
						</p>
					)}
				</article>
			) : (
				// Placeholder to maintain scroll height while off-screen (content-visibility handles the rest)
				<div aria-hidden="true" style={{ minHeight: "900px" }} />
			)}

			{/* Selection Menu */}
			{selectionMenu && (
				<div
					role="toolbar"
					aria-label="Selection menu"
					className="selection-menu absolute z-50 flex gap-1 bg-white border border-slate-200 text-slate-900 p-1.5 rounded-lg shadow-xl overflow-hidden transform -translate-x-1/2 gpu-accelerated"
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
									selectionMenu.context,
									selectionMenu.coords,
								);
							clearSelectionMenu();
						}}
						className="px-4 py-2.5 sm:py-2 hover:bg-slate-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-100 min-h-[44px] sm:min-h-0"
					>
						<span>文A</span> {t("menu.translate", "Translate")}
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
								clearSelectionMenu();
							}}
							className="px-4 py-2.5 sm:py-2 hover:bg-slate-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-100 min-h-[44px] sm:min-h-0"
						>
							<span>💡</span> {t("menu.explain", "Explain")}
						</button>
					)}

					<button
						type="button"
						onClick={(e) => {
							e.stopPropagation();
							if (onTextSelect)
								onTextSelect(selectionMenu.text, selectionMenu.coords);
							clearSelectionMenu();
						}}
						className="px-4 py-2.5 sm:py-2 hover:bg-slate-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors rounded-r-lg min-h-[44px] sm:min-h-0"
					>
						<span>📝</span> {t("menu.note", "Note")}
					</button>

					{/* Triangle arrow */}
					<div className="absolute left-1/2 top-0 w-2 h-2 bg-white border-l border-t border-slate-200 transform -translate-x-1/2 -translate-y-1/2 rotate-45 pointer-events-none" />
				</div>
			)}

			{/* Zoom Modal — body にポータル描画して viewport 基準で表示 */}
			{zoomedImage &&
				createPortal(
					<div className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-8 overflow-hidden animate-fade-in">
						<button
							type="button"
							className="absolute inset-0 w-full h-full bg-black/80 cursor-pointer border-none"
							onClick={() => setZoomedImage(null)}
							aria-label="Close zoom backdrop"
						/>
						<button
							type="button"
							className="absolute top-6 right-6 text-white/70 hover:text-white p-2 hover:bg-white/10 rounded-full transition-all z-[110]"
							onClick={() => setZoomedImage(null)}
							aria-label="Close zoom"
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
							className="relative max-w-5xl w-full flex items-center justify-center pointer-events-none"
						>
							<img
								src={zoomedImage}
								alt="Zoomed figure"
								className="max-w-full max-h-[90vh] object-contain shadow-2xl rounded-lg pointer-events-auto cursor-default"
							/>
						</div>
					</div>,
					document.body,
				)}
		</div>
	);
};

export default React.memo(TextModePage);

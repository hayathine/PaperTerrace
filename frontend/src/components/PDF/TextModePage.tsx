import React, { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Components } from "react-markdown";
import { API_URL } from "../../config";
import { useIntersectionObserver } from "../../hooks/useIntersectionObserver";
import MarkdownContent from "../Common/MarkdownContent";
import type { Figure, PageWithLines } from "./types";

const KNOWN_SECTIONS = [
	"abstract",
	"introduction",
	"conclusion",
	"conclusions",
	"related work",
	"references",
	"bibliography",
	"acknowledgement",
	"acknowledgements",
	"methods",
	"methodology",
	"discussion",
	"results",
	"experiments",
	"evaluation",
];

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
	onAskAI?: (
		prompt: string,
		imageUrl?: string,
		coords?: any,
		originalText?: string,
		contextText?: string,
	) => void;
	searchTerm?: string;
}

/**
 * searchTerm にマッチする部分を <mark> で囲んだ React ノードを返す。
 * children が文字列以外（React要素など）の場合は再帰的に処理する。
 *
 * パフォーマンス:
 * - lowerTerm は呼び出し元で一度だけ計算し、再帰に渡す。
 * - 文字列の走査は indexOf を lastIdx から進めるため O(n)。
 * - React 要素ツリーの走査は O(ノード数)。
 */
function highlightText(
	children: React.ReactNode,
	searchTerm: string,
	lowerTerm?: string,
): React.ReactNode {
	if (!searchTerm || searchTerm.length < 2) return children;

	// lowerTerm は最初の呼び出しでのみ計算し、再帰時は引数で渡す
	const term = lowerTerm ?? searchTerm.toLowerCase();

	if (typeof children === "string") {
		const lowerText = children.toLowerCase();
		const firstIdx = lowerText.indexOf(term);
		if (firstIdx === -1) return children;

		const parts: React.ReactNode[] = [];
		let lastIdx = 0;
		let pos = firstIdx;
		let key = 0;
		while (pos !== -1) {
			if (pos > lastIdx) {
				parts.push(children.slice(lastIdx, pos));
			}
			parts.push(
				<mark key={key++} className="bg-amber-300/70 rounded px-0.5">
					{children.slice(pos, pos + searchTerm.length)}
				</mark>,
			);
			lastIdx = pos + searchTerm.length;
			pos = lowerText.indexOf(term, lastIdx);
		}
		if (lastIdx < children.length) {
			parts.push(children.slice(lastIdx));
		}
		return <>{parts}</>;
	}

	if (Array.isArray(children)) {
		return children.map((child, i) => (
			<React.Fragment key={i}>
				{highlightText(child, searchTerm, term)}
			</React.Fragment>
		));
	}

	if (React.isValidElement(children)) {
		const element = children as React.ReactElement<{
			className?: string;
			children?: React.ReactNode;
		}>;
		// rehype-katex が生成する math/KaTeX 要素はスキップ（内部構造を破壊しないため）
		const className = element.props.className ?? "";
		if (
			typeof className === "string" &&
			(className.includes("math") || className.includes("katex"))
		) {
			return children;
		}
		if (element.props.children != null) {
			return React.cloneElement(element, {
				...element.props,
				children: highlightText(element.props.children, searchTerm, term),
			});
		}
	}

	return children;
}

function extractHeadingText(node: React.ReactNode): string {
	if (typeof node === "string") return node;
	if (Array.isArray(node)) return node.map(extractHeadingText).join("");
	if (React.isValidElement(node)) {
		return extractHeadingText(
			(node.props as { children?: React.ReactNode }).children,
		);
	}
	return "";
}

/**
 * バックエンドが出力する `![Figure]([x1, y1, x2, y2])` 形式の alt/src から
 * bbox を抽出し、page.figures の実画像 URL にマッピングする。
 */
function parseBboxFromSrc(src: string): number[] | null {
	const match = src.match(
		/\[?\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\]?/,
	);
	if (!match) return null;
	return [
		Number.parseFloat(match[1]),
		Number.parseFloat(match[2]),
		Number.parseFloat(match[3]),
		Number.parseFloat(match[4]),
	];
}

function findFigureByBbox(
	figures: Figure[] | undefined,
	bbox: number[],
	tolerance = 20,
): Figure | undefined {
	if (!Array.isArray(figures) || figures.length === 0) return undefined;
	return figures.find((fig) => {
		const [fx1, fy1, fx2, fy2] = fig.bbox;
		return (
			Math.abs(fx1 - bbox[0]) < tolerance &&
			Math.abs(fy1 - bbox[1]) < tolerance &&
			Math.abs(fx2 - bbox[2]) < tolerance &&
			Math.abs(fy2 - bbox[3]) < tolerance
		);
	});
}

const TextModePage: React.FC<TextModePageProps> = ({
	page,
	onWordClick,
	onTextSelect,
	onAskAI,
	searchTerm,
}) => {
	const { t } = useTranslation();

	// Intersection Observer: delay heavy Markdown rendering until page is near viewport
	const containerRef = useRef<HTMLDivElement>(null);
	const isVisible = useIntersectionObserver(containerRef, {
		rootMargin: "400px",
	});

	const [selectionMenu, setSelectionMenu] = React.useState<{
		x: number;
		y: number;
		text: string;
		context: string;
		coords: any;
	} | null>(null);
	const [zoomedImage, setZoomedImage] = useState<string | null>(null);
	// setTimeout のタイマー ID を ref で管理し、連続イベントで前のタイマーをキャンセルする
	const selectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// --- テキスト選択メニュー ---
	React.useEffect(() => {
		const handleSelectionEnd = () => {
			// 前のタイマーをキャンセルして競合状態を防ぐ
			if (selectionTimerRef.current !== null) {
				clearTimeout(selectionTimerRef.current);
			}
			selectionTimerRef.current = setTimeout(() => {
				selectionTimerRef.current = null;
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

					if (
						!container.contains(range.startContainer) &&
						range.startContainer !== container
					) {
						return;
					}

					const rect = container.getBoundingClientRect();
					const rangeRect = range.getBoundingClientRect();

					if (rangeRect.width === 0) return;

					const pageWidth = rect.width || 1;
					const pageHeight = rect.height || 1;

					// Clamp menu X to avoid overflow near screen edges (10%–90% of page width)
					const rawMenuX =
						(((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth) *
						100;
					const menuX = Math.max(10, Math.min(90, rawMenuX));
					const menuY = ((rangeRect.bottom - rect.top) / pageHeight) * 100;

					const centerX =
						((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth;
					const centerY =
						((rangeRect.top + rangeRect.bottom) / 2 - rect.top) / pageHeight;

					// Extract context text (parent paragraph or surrounding text)
					let contextText = selectionText;
					let currentEl = range.startContainer.parentElement;
					while (currentEl && currentEl !== container) {
						if (
							["P", "LI", "H1", "H2", "H3", "H4", "H5", "H6"].includes(
								currentEl.tagName,
							)
						) {
							contextText = currentEl.textContent || selectionText;
							break;
						}
						currentEl = currentEl.parentElement;
					}

					setSelectionMenu({
						x: menuX,
						y: menuY,
						text: selectionText,
						context: contextText,
						coords: { page: page.page_num, x: centerX, y: centerY },
					});
				} else {
					setSelectionMenu(null);
				}
			}, 10);
		};

		// Support both mouse and touch text selection
		document.addEventListener("mouseup", handleSelectionEnd);
		document.addEventListener("touchend", handleSelectionEnd);
		return () => {
			document.removeEventListener("mouseup", handleSelectionEnd);
			document.removeEventListener("touchend", handleSelectionEnd);
			// アンマウント時に残存タイマーをキャンセル
			if (selectionTimerRef.current !== null) {
				clearTimeout(selectionTimerRef.current);
			}
		};
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
					if (figure) {
						// /static/... の相対パスの場合は API_URL プレフィックスを付与
						const imgSrc = figure.image_url.startsWith("http")
							? figure.image_url
							: `${API_URL}${figure.image_url}`;

						const isEquation =
							figure.label?.toLowerCase() === "equation" ||
							(typeof alt === "string" &&
								alt.toLowerCase().includes("equation"));

						return (
							<img
								src={imgSrc}
								alt={alt || figure.label || "Figure"}
								onClick={() => setZoomedImage(imgSrc)}
								className={`
									mx-auto my-4 rounded shadow-sm border border-slate-200 object-contain cursor-zoom-in hover:brightness-[0.98] transition-all
									${isEquation ? "max-h-24 w-auto max-w-[90%]" : "max-w-full h-auto"}
								`.trim()}
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
			const isEquationGeneric =
				typeof alt === "string" && alt.toLowerCase().includes("equation");

			return (
				<img
					src={src}
					alt={alt}
					onClick={() => src && setZoomedImage(src)}
					className={`
						mx-auto my-4 rounded shadow-sm object-contain cursor-zoom-in hover:brightness-[0.98] transition-all
						${isEquationGeneric ? "max-h-24 w-auto max-w-[90%]" : "max-w-full h-auto"}
					`.trim()}
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
			</div>

			{/* Markdown Content - lazy render when off-screen to save React/browser work */}
			{isVisible ? (
				<div className="px-3 py-4 sm:px-6 sm:py-5 md:px-10 md:py-8 selection:bg-orange-600/30 overflow-x-hidden">
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
				</div>
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
							setSelectionMenu(null);
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
								setSelectionMenu(null);
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
							setSelectionMenu(null);
						}}
						className="px-4 py-2.5 sm:py-2 hover:bg-slate-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors rounded-r-lg min-h-[44px] sm:min-h-0"
					>
						<span>📝</span> {t("menu.note", "Comment")}
					</button>

					{/* Triangle arrow */}
					<div className="absolute left-1/2 top-0 w-2 h-2 bg-white border-l border-t border-slate-200 transform -translate-x-1/2 -translate-y-1/2 rotate-45 pointer-events-none" />
				</div>
			)}

			{/* Zoom Modal */}
			{zoomedImage && (
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
						className="relative max-w-5xl w-full max-h-full flex items-center justify-center pointer-events-none"
					>
						<img
							src={zoomedImage}
							alt="Zoomed figure"
							className="max-w-full max-h-[90vh] object-contain shadow-2xl rounded-lg pointer-events-auto cursor-default"
						/>
					</div>
				</div>
			)}
		</div>
	);
};

export default React.memo(TextModePage);

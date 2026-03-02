import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Components } from "react-markdown";
import { API_URL } from "../../config";
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
	onAskAI?: (prompt: string, imageUrl?: string, coords?: any) => void;
	searchTerm?: string;
}

/**
 * searchTerm にマッチする部分を <mark> で囲んだ React ノードを返す。
 * children が文字列以外（React要素など）の場合は再帰的に処理する。
 */
function highlightText(
	children: React.ReactNode,
	searchTerm: string,
): React.ReactNode {
	if (!searchTerm || searchTerm.length < 2) return children;

	if (typeof children === "string") {
		const lowerText = children.toLowerCase();
		const lowerTerm = searchTerm.toLowerCase();
		const idx = lowerText.indexOf(lowerTerm);
		if (idx === -1) return children;

		const parts: React.ReactNode[] = [];
		let lastIdx = 0;
		let pos = idx;
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
			pos = lowerText.indexOf(lowerTerm, lastIdx);
		}
		if (lastIdx < children.length) {
			parts.push(children.slice(lastIdx));
		}
		return <>{parts}</>;
	}

	if (Array.isArray(children)) {
		return children.map((child, i) => (
			<React.Fragment key={i}>
				{highlightText(child, searchTerm)}
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
		if (element.props.children) {
			return React.cloneElement(element, {
				...element.props,
				children: highlightText(element.props.children, searchTerm),
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
	if (!figures || figures.length === 0) return undefined;
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
	const [selectionMenu, setSelectionMenu] = React.useState<{
		x: number;
		y: number;
		text: string;
		coords: any;
	} | null>(null);

	// --- テキスト選択メニュー ---
	React.useEffect(() => {
		const handleSelectionEnd = () => {
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

					setSelectionMenu({
						x: menuX,
						y: menuY,
						text: selectionText,
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
	const markdownText = useMemo(() => {
		if (page.content && page.content.trim().length > 0) {
			return page.content;
		}
		// フォールバック: lines のワードを結合
		if (page.lines && page.lines.length > 0) {
			return page.lines
				.map((line) => line.words.map((w) => w.word).join(" "))
				.join("\n");
		}
		return "";
	}, [page.content, page.lines]);

	// --- Markdown 前処理: 表ブロック → 表画像マーカー置換 ---
	// バックエンドが生成する "| col | col |" 形式の Markdown 表を、
	// page.figures の label='table' 実画像に差し替えることで視覚的な表を表示する。
	const processedMarkdown = useMemo(() => {
		if (!markdownText) return markdownText;

		const tableFigures = (page.figures ?? [])
			.filter((f) => (f.label ?? "").toLowerCase() === "table")
			.sort((a, b) => a.bbox[1] - b.bbox[1]);

		if (tableFigures.length === 0) return markdownText;

		let tableIdx = 0;
		return markdownText.replace(/((?:\|[^\n]*\n?)+)/g, (match) => {
			if (tableIdx < tableFigures.length) {
				const fig = tableFigures[tableIdx++];
				const [x1, y1, x2, y2] = fig.bbox;
				return `\n![Table]([${x1}, ${y1}, ${x2}, ${y2}])\n`;
			}
			// 対応する figure がない場合は元のテキストを維持
			return match;
		});
	}, [markdownText, page.figures]);

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
						return (
							<img
								src={imgSrc}
								alt={alt || figure.label || "Figure"}
								className="max-w-full h-auto mx-auto my-4 rounded shadow-sm border border-slate-200"
								loading="lazy"
								{...rest}
							/>
						);
					}
					// マッチしない場合はプレースホルダー
					return (
						<div className="flex items-center justify-center bg-slate-100 border border-dashed border-slate-300 rounded p-6 my-4 text-slate-400 text-sm">
							{alt || "Figure"} (image not available)
						</div>
					);
				}
			}
			// 通常の画像
			return (
				<img
					src={src}
					alt={alt}
					className="max-w-full h-auto mx-auto my-4 rounded shadow-sm"
					loading="lazy"
					{...rest}
				/>
			);
		};

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

		// 検索ハイライト: テキスト要素をラップ
		if (searchTerm && searchTerm.length >= 2) {
			comps.p = ({ children, ...rest }) => (
				<p {...rest}>{highlightText(children, searchTerm)}</p>
			);
			comps.li = ({ children, ...rest }) => (
				<li {...rest}>{highlightText(children, searchTerm)}</li>
			);
			comps.td = ({ children, ...rest }) => (
				<td {...rest}>{highlightText(children, searchTerm)}</td>
			);
			comps.th = ({ children, ...rest }) => (
				<th {...rest}>{highlightText(children, searchTerm)}</th>
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
					className="text-2xl font-bold text-slate-800 leading-snug tracking-tight mt-2 mb-6 pb-4 border-b-2 border-slate-300"
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
					className={`text-base font-bold mt-8 mb-3 pb-1 border-b ${
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
					className="text-sm font-bold text-slate-700 mt-6 mb-2 pl-2 border-l-2 border-slate-300"
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
					className="text-sm font-semibold text-slate-600 mt-4 mb-1.5 italic"
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
			id={`text-page-${page.page_num}`}
			className="relative shadow-sm bg-white border border-slate-200 group mx-auto w-full"
			style={{ userSelect: "auto" }}
		>
			{/* Header */}
			<div className="bg-slate-50 border-b border-slate-200 px-4 py-1.5 flex justify-between items-center select-none">
				<span className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">
					Page {page.page_num}
				</span>
			</div>

			{/* Markdown Content */}
			<div className="px-3 py-4 sm:px-6 sm:py-5 md:px-10 md:py-8 selection:bg-orange-600/30">
				{processedMarkdown ? (
					<MarkdownContent
						className="prose prose-slate max-w-none prose-p:my-3 prose-p:leading-7 prose-li:my-1 prose-li:leading-7 prose-img:mx-auto [&_.katex]:text-base [&_.katex]:font-normal [&_.katex-display]:my-4 [&_.math-display]:block [&_.katex-display]:overflow-x-auto [&_.katex-display]:max-w-full prose-pre:overflow-x-auto"
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

			{/* Selection Menu */}
			{selectionMenu && (
				<div
					role="toolbar"
					aria-label="Selection menu"
					className="selection-menu absolute z-50 flex gap-1 bg-white border border-slate-200 text-slate-900 p-1.5 rounded-lg shadow-xl overflow-hidden transform -translate-x-1/2"
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
						className="px-4 py-2.5 sm:py-2 hover:bg-orange-100 text-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors border-r border-slate-100 min-h-[44px] sm:min-h-0"
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
						className={`px-4 py-2.5 sm:py-2 hover:bg-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors min-h-[44px] sm:min-h-0 ${onAskAI ? "border-r border-slate-700" : ""}`}
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
							className="px-4 py-2.5 sm:py-2 hover:bg-orange-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 transition-colors rounded-r-lg min-h-[44px] sm:min-h-0"
						>
							<span>💡</span> {t("menu.explain", "Explain")}
						</button>
					)}

					{/* Triangle arrow */}
					<div className="absolute left-1/2 top-0 w-2 h-2 bg-white border-l border-t border-slate-200 transform -translate-x-1/2 -translate-y-1/2 rotate-45 pointer-events-none" />
				</div>
			)}
		</div>
	);
};

export default React.memo(TextModePage);

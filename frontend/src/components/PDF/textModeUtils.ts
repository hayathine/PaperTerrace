import React from "react";
import type { Figure } from "./types";

/** テキストモードで折り畳みスタイルを適用する既知のセクション名。 */
export const KNOWN_SECTIONS = [
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

/**
 * searchTerm にマッチする部分を <mark> で囲んだ React ノードを返す。
 * children が文字列以外（React要素など）の場合は再帰的に処理する。
 *
 * パフォーマンス:
 * - lowerTerm は呼び出し元で一度だけ計算し、再帰に渡す。
 * - 文字列の走査は indexOf を lastIdx から進めるため O(n)。
 * - React 要素ツリーの走査は O(ノード数)。
 */
export function highlightText(
	children: React.ReactNode,
	searchTerm: string,
	lowerTerm?: string,
): React.ReactNode {
	if (!searchTerm || searchTerm.length < 2) return children;

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
				React.createElement(
					"mark",
					{ key: key++, className: "bg-amber-300/70 rounded px-0.5" },
					children.slice(pos, pos + searchTerm.length),
				),
			);
			lastIdx = pos + searchTerm.length;
			pos = lowerText.indexOf(term, lastIdx);
		}
		if (lastIdx < children.length) {
			parts.push(children.slice(lastIdx));
		}
		return React.createElement(React.Fragment, null, ...parts);
	}

	if (Array.isArray(children)) {
		return children.map((child, i) =>
			React.createElement(
				React.Fragment,
				{ key: i },
				highlightText(child, searchTerm, term),
			),
		);
	}

	if (React.isValidElement(children)) {
		const element = children as React.ReactElement<{
			className?: string;
			children?: React.ReactNode;
		}>;
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

/** React ノードツリーから見出しのプレーンテキストを再帰的に抽出する。 */
export function extractHeadingText(node: React.ReactNode): string {
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
export function parseBboxFromSrc(src: string): number[] | null {
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

/** bbox の近似一致でページ内の Figure オブジェクトを検索する。 */
export function findFigureByBbox(
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

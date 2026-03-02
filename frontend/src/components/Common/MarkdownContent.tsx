import type React from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import { preprocessMathUnicode } from "../../lib/mathPreprocess";

interface MarkdownContentProps {
	children: string;
	className?: string;
	/** react-markdown の components を上書きしてカスタムレンダリングする場合に指定 */
	components?: Components;
}

/**
 * Markdown + LaTeX 対応のテキストレンダラー。
 * remark-math でインライン ($...$) / ブロック ($$...$$) 数式を検出し、
 * rehype-katex で KaTeX へ変換する。
 *
 * KaTeX が Main-Regular フォントのメトリクスを持たない Unicode 文字（∆, ◦ など）は
 * preprocessMathUnicode で LaTeX コマンドへ変換してから渡す。
 * 変換できない残余記号は unknownSymbol エラーを無視することで警告を抑制する。
 */
const MarkdownContent: React.FC<MarkdownContentProps> = ({
	children,
	className = "",
	components,
}) => {
	const processedContent = preprocessMathUnicode(children);

	return (
		<div className={className}>
			<ReactMarkdown
				remarkPlugins={[remarkMath]}
				rehypePlugins={[
					[
						rehypeKatex,
						{
							// unknownSymbol（フォントメトリクス欠落）は無視し、他の警告は保持する
							strict: (errorCode: string) =>
								errorCode === "unknownSymbol" ? "ignore" : "warn",
						},
					],
				]}
				components={components}
			>
				{processedContent}
			</ReactMarkdown>
		</div>
	);
};

export default MarkdownContent;

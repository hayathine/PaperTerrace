import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

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
 */
const MarkdownContent: React.FC<MarkdownContentProps> = ({
	children,
	className = "",
	components,
}) => {
	return (
		<div className={className}>
			<ReactMarkdown
				remarkPlugins={[remarkMath]}
				rehypePlugins={[rehypeKatex]}
				components={components}
			>
				{children}
			</ReactMarkdown>
		</div>
	);
};

export default MarkdownContent;

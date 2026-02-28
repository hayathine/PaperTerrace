import type React from "react";
import { useCallback, useState } from "react";

interface CopyButtonProps {
	/** コピー対象のテキスト */
	text: string;
	/** ボタンのサイズ（アイコンのwidthとheight） */
	size?: number;
	/** 追加のCSSクラス */
	className?: string;
}

/**
 * クリップボードにテキストをコピーするボタン。
 * コピー成功時にチェックマークアイコンに切り替わり、2秒後に元に戻る。
 */
const CopyButton: React.FC<CopyButtonProps> = ({
	text,
	size = 14,
	className = "",
}) => {
	const [copied, setCopied] = useState(false);

	const handleCopy = useCallback(async () => {
		try {
			await navigator.clipboard.writeText(text);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		} catch {
			// フォールバック: 古いブラウザ対応
			const textarea = document.createElement("textarea");
			textarea.value = text;
			textarea.style.position = "fixed";
			textarea.style.opacity = "0";
			document.body.appendChild(textarea);
			textarea.select();
			document.execCommand("copy");
			document.body.removeChild(textarea);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}
	}, [text]);

	return (
		<button
			type="button"
			onClick={handleCopy}
			className={`p-1 rounded transition-all ${
				copied
					? "text-green-500"
					: "text-slate-300 hover:text-slate-500 hover:bg-slate-100"
			} ${className}`}
			title={copied ? "Copied!" : "Copy"}
		>
			{copied ? (
				<svg
					width={size}
					height={size}
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					strokeWidth={2}
					strokeLinecap="round"
					strokeLinejoin="round"
				>
					<path d="M20 6L9 17l-5-5" />
				</svg>
			) : (
				<svg
					width={size}
					height={size}
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					strokeWidth={2}
					strokeLinecap="round"
					strokeLinejoin="round"
				>
					<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
					<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
				</svg>
			)}
		</button>
	);
};

export default CopyButton;

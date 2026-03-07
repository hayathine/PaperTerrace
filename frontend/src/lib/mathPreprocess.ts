/**
 * KaTeX が Main-Regular フォントのメトリクスを持たない Unicode 文字を
 * 対応する LaTeX コマンドへ変換するユーティリティ。
 *
 * 変換はインライン数式 ($...$) およびブロック数式 ($$...$$) の内部にのみ適用し、
 * コードブロック (``` / `) は変換対象から除外する。
 * 変換できない残余記号は rehype-katex の strict 設定で無視する。
 */

// 数式内で置換する Unicode → LaTeX コマンドのマッピング
const MATH_UNICODE_MAP: Array<[RegExp, string]> = [
	[/∆/g, "\\Delta "], // U+2206 INCREMENT (∆ ≠ Δ U+0394)
	[/◦/g, "\\circ "], // U+25E6 WHITE BULLET (◦ ≠ ∘ U+2218 RING OPERATOR)
	[/∇/g, "\\nabla "], // U+2207 NABLA
	[/∈/g, "\\in "], // U+2208
	[/∉/g, "\\notin "], // U+2209
	[/⊆/g, "\\subseteq "], // U+2286
	[/⊂/g, "\\subset "], // U+2282
	[/∪/g, "\\cup "], // U+222A
	[/∩/g, "\\cap "], // U+2229
	[/≤/g, "\\leq "], // U+2264
	[/≥/g, "\\geq "], // U+2265
	[/≠/g, "\\neq "], // U+2260
	[/≈/g, "\\approx "], // U+2248
	[/∞/g, "\\infty "], // U+221E
	[/→/g, "\\rightarrow "], // U+2192
	[/←/g, "\\leftarrow "], // U+2190
	[/↔/g, "\\leftrightarrow "], // U+2194
	[/⇒/g, "\\Rightarrow "], // U+21D2
	[/⇔/g, "\\Leftrightarrow "], // U+21D4
	[/∀/g, "\\forall "], // U+2200
	[/∃/g, "\\exists "], // U+2203
	[/¬/g, "\\neg "], // U+00AC
	[/∧/g, "\\land "], // U+2227
	[/∨/g, "\\lor "], // U+2228
	[/×/g, "\\times "], // U+00D7
	[/÷/g, "\\div "], // U+00F7
	[/±/g, "\\pm "], // U+00B1
	[/∑/g, "\\sum "], // U+2211
	[/∏/g, "\\prod "], // U+220F
	[/∫/g, "\\int "], // U+222B
];

/** 数式文字列内の Unicode 記号を LaTeX コマンドに置換する */
function replaceMathSymbols(math: string): string {
	let result = math;
	for (const [pattern, replacement] of MATH_UNICODE_MAP) {
		result = result.replace(pattern, replacement);
	}
	return result;
}

/**
 * コードブロックを除くテキスト部分の数式内を変換する。
 * $$...$$ → インナーを置換して再組み立て
 * $...$   → 同上
 */
function replaceMathInSegment(segment: string): string {
	return segment
		.replace(
			/\$\$([\s\S]*?)\$\$/g,
			(_, inner) => `$$${replaceMathSymbols(inner)}$$`,
		)
		.replace(/\$([^$\n]+?)\$/g, (_, inner) => `$${replaceMathSymbols(inner)}$`);
}

/**
 * Markdown 文字列を受け取り、コードブロック外の数式内にある
 * KaTeX 未対応 Unicode 文字を LaTeX コマンドへ変換して返す。
 */
export function preprocessMathUnicode(content: string): string {
	const parts: string[] = [];
	let lastIndex = 0;

	// バッククォート3つのフェンスブロック、またはインラインコードを検出してスキップ
	const codePattern = /(`{3}[\s\S]*?`{3}|`[^`\n]*`)/g;
	let match: RegExpExecArray | null;

	// biome-ignore lint/suspicious/noAssignInExpressions: iteration idiom
	while ((match = codePattern.exec(content)) !== null) {
		parts.push(replaceMathInSegment(content.slice(lastIndex, match.index)));
		parts.push(match[0]); // コードブロックはそのまま保持
		lastIndex = match.index + match[0].length;
	}

	parts.push(replaceMathInSegment(content.slice(lastIndex)));
	return parts.join("");
}

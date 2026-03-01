"""
Math/LaTeX utilities shared between backend services.

Provides lightweight, heuristic-based post-processing to improve
the readability of math extracted from PDFs (especially from pymupdf4llm).
No AI or specialized OCR is used — all transformations are rule-based.
"""

import re

# ---------------------------------------------------------------------------
# Unicode math symbol → LaTeX command mapping
# Applied only when text is already inside a $...$ / $$...$$ block, or when
# constructing a new $$ block from detected equation bboxes.
# ---------------------------------------------------------------------------
MATH_UNICODE_LATEX: dict[str, str] = {
    # Delimiters
    "⟨": r"\langle ",
    "⟩": r"\rangle ",
    "⟪": r"\langle\langle ",
    "⟫": r"\rangle\rangle ",
    # Relations
    "≤": r"\leq ",
    "≥": r"\geq ",
    "≠": r"\neq ",
    "≈": r"\approx ",
    "≡": r"\equiv ",
    "∝": r"\propto ",
    "∼": r"\sim ",
    "≃": r"\simeq ",
    # Set / logic
    "∈": r"\in ",
    "∉": r"\notin ",
    "⊂": r"\subset ",
    "⊃": r"\supset ",
    "⊆": r"\subseteq ",
    "⊇": r"\supseteq ",
    "∩": r"\cap ",
    "∪": r"\cup ",
    "∀": r"\forall ",
    "∃": r"\exists ",
    "∧": r"\wedge ",
    "∨": r"\vee ",
    "¬": r"\neg ",
    "∅": r"\emptyset ",
    # Arrows
    "→": r"\to ",
    "←": r"\leftarrow ",
    "↔": r"\leftrightarrow ",
    "⇒": r"\Rightarrow ",
    "⇐": r"\Leftarrow ",
    "⇔": r"\Leftrightarrow ",
    "↑": r"\uparrow ",
    "↓": r"\downarrow ",
    # Operators
    "∑": r"\sum ",
    "∏": r"\prod ",
    "∫": r"\int ",
    "∂": r"\partial ",
    "∇": r"\nabla ",
    "∞": r"\infty ",
    "±": r"\pm ",
    "∓": r"\mp ",
    "×": r"\times ",
    "÷": r"\div ",
    "·": r"\cdot ",
    "∗": "*",
    "†": r"\dagger ",
    "‡": r"\ddagger ",
    "√": r"\sqrt",
    # Blackboard bold
    "ℝ": r"\mathbb{R}",
    "ℤ": r"\mathbb{Z}",
    "ℚ": r"\mathbb{Q}",
    "ℕ": r"\mathbb{N}",
    "ℂ": r"\mathbb{C}",
    "𝔼": r"\mathbb{E}",
    # Greek lowercase
    "α": r"\alpha ",
    "β": r"\beta ",
    "γ": r"\gamma ",
    "δ": r"\delta ",
    "ε": r"\varepsilon ",
    "ζ": r"\zeta ",
    "η": r"\eta ",
    "θ": r"\theta ",
    "ι": r"\iota ",
    "κ": r"\kappa ",
    "λ": r"\lambda ",
    "μ": r"\mu ",
    "µ": r"\mu ",  # U+00B5 MICRO SIGN (distinct from μ U+03BC)
    "ν": r"\nu ",
    "ξ": r"\xi ",
    "π": r"\pi ",
    "ρ": r"\rho ",
    "σ": r"\sigma ",
    "τ": r"\tau ",
    "υ": r"\upsilon ",
    "φ": r"\varphi ",
    "χ": r"\chi ",
    "ψ": r"\psi ",
    "ω": r"\omega ",
    # Greek uppercase (only those with dedicated LaTeX commands)
    "Γ": r"\Gamma ",
    "Δ": r"\Delta ",
    "Θ": r"\Theta ",
    "Λ": r"\Lambda ",
    "Ξ": r"\Xi ",
    "Π": r"\Pi ",
    "Σ": r"\Sigma ",
    "Υ": r"\Upsilon ",
    "Φ": r"\Phi ",
    "Ψ": r"\Psi ",
    "Ω": r"\Omega ",
}

# Characters that indicate math content (used for density checks)
_MATH_CHARS: frozenset[str] = frozenset(
    "⟨⟩⟪⟫≤≥≠≈≡∝∼≃∈∉⊂⊃⊆⊇∩∪∀∃∧∨¬∅→←↔⇒⇐⇔↑↓"
    "∑∏∫∂∇∞±∓×÷·∗†‡√ℝℤℚℕℂ𝔼"
    "αβγδεζηθικλμµνξπρστυφχψω"
    "ΓΔΘΛΞΠΣΥΦΨΩ"
)


def unicode_math_to_latex(text: str) -> str:
    """
    Unicode 数学記号を LaTeX コマンドに変換する。
    $$...$$ ブロック内のテキストに適用することを想定している。
    通常の本文テキストには適用しないこと（誤変換を防ぐため）。
    """
    for char, latex in MATH_UNICODE_LATEX.items():
        text = text.replace(char, latex)
    return text


def convert_superscript_brackets(text: str) -> str:
    """
    pymupdf4llm が生成する [char] 記法（上付き文字の表現）を
    LaTeX の ^{char} に変換する。

    変換しないケース:
    - [1], [12] など純粋な数字列 → 引用文献の可能性が高い
    - [...] の前後にスペースがある場合 → 角括弧としての用途が高い

    例:
      Π[∗]  →  Π^{∗}
      [x,m] →  ^{x,m}
    """

    def _replace(m: re.Match) -> str:
        inner = m.group(1)
        # 純粋な数字のみ（引用 [1], [23] 等）は変換しない
        if re.fullmatch(r"\d+", inner):
            return m.group(0)
        # 空白を含む長い括弧表現は通常の文章表現の可能性があるため除外
        if " " in inner and len(inner) > 6:
            return m.group(0)
        return f"^{{{inner}}}"

    return re.sub(r"\[([^\[\]\n]{1,20})\]", _replace, text)


def has_math_content(text: str, min_chars: int = 2) -> bool:
    """テキストに数学記号が min_chars 個以上含まれているか判定する。"""
    return sum(1 for c in text if c in _MATH_CHARS) >= min_chars


def wrap_equation_block(raw_text: str) -> str:
    """
    数式ブロックのテキストを $$...$$ でラップし、
    Unicode→LaTeX 変換と superscript bracket 変換を適用する。
    """
    latex = unicode_math_to_latex(raw_text)
    latex = convert_superscript_brackets(latex)
    # 改行を空白に正規化
    latex = " ".join(latex.split())
    return f"$$\n{latex}\n$$"


def replace_equation_paragraph(
    markdown: str,
    eq_words: list[str],
    latex_block: str,
    min_match: int = 3,
) -> tuple[str, bool]:
    """
    pymupdf4llm が生成した Markdown 内で、eq_words に対応する段落を
    latex_block に置換する。

    Returns:
        (updated_markdown, was_replaced)
    """
    if not eq_words:
        return markdown, False

    # 長さ 2 以上の単語だけを照合キーとして使う（ノイズ除去）
    key_tokens = [w for w in eq_words if len(w) >= 2][:10]
    if not key_tokens:
        return markdown, False

    paragraphs = re.split(r"(\n{2,})", markdown)
    for i, para in enumerate(paragraphs):
        # 既に数式ブロックの場合はスキップ
        stripped = para.strip()
        if stripped.startswith("$$") or stripped.startswith("$"):
            continue
        match_count = sum(1 for t in key_tokens if t in para)
        if match_count >= min(min_match, len(key_tokens)):
            paragraphs[i] = f"\n\n{latex_block}\n\n"
            return "".join(paragraphs), True

    return markdown, False

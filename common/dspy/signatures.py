import dspy

from common.prompts import (
    AGENT_ADVERSARIAL_CRITIQUE_PROMPT,
    CHAT_AUTHOR_PERSONA_PROMPT,
    CHAT_GENERAL_RESPONSE_PROMPT,
    CORE_SYSTEM_PROMPT,
    PAPER_SUMMARY_AI_CONTEXT_PROMPT,
    PAPER_SUMMARY_FULL_PROMPT,
    PAPER_SUMMARY_SECTIONS_PROMPT,
    VISION_ANALYZE_FIGURE_PROMPT,
)


# -------------------------------------------------------------
# 1. 既存プロンプトをDSPy向けにクリーンアップするユーティリティ
# -------------------------------------------------------------
def clean_prompt_for_dspy(prompt_str: str) -> str:
    """
    prompts.py の文字列から DSPy にとってノイズになるプレースホルダー等を除去し、
    最適化可能性を高めたクリーンな Instruction（__doc__ 用）を生成する。
    """
    cleaned = prompt_str
    # プレースホルダーを汎用的な指示表現に置換
    cleaned = cleaned.replace("PAPER_TEXT: {paper_text}", "")
    cleaned = cleaned.replace("{paper_text}", "the provided paper text")
    cleaned = cleaned.replace("{lang_name}", "the specified target language")
    cleaned = cleaned.replace("{document_context}", "the provided academic context")
    cleaned = cleaned.replace("{history_text}", "the conversation history")
    cleaned = cleaned.replace("{text}", "the provided text")
    cleaned = cleaned.replace("{question}", "the user's question")
    cleaned = cleaned.replace("{caption_hint}", "the provided caption")
    cleaned = cleaned.replace("{context_hint}", "the context hint")
    cleaned = cleaned.replace("{table_text}", "the table text")
    cleaned = cleaned.replace("{paragraph}", "the paragraph text")

    # Core Promptを結合して、安定した品質のベースラインとする
    return f"{CORE_SYSTEM_PROMPT}\n\n[Task Instructions]\n{cleaned}".strip()


# =============================================================
# Analysis (解析系) の DSPy Signatures
# =============================================================


# =============================================================
# Summary (要約系) の DSPy Signatures
# =============================================================


class PaperSummary(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_FULL_PROMPT)
    paper_text: str = dspy.InputField(desc="論文の全文テキスト")
    lang_name: str = dspy.InputField(desc="出力する言語（例: Japanese）")
    overview: str = dspy.OutputField(desc="概要・全体像 (1-2 sentences)")
    key_contributions: list[str] = dspy.OutputField(desc="主な貢献・新規点 (3-5 items)")
    methodology: str = dspy.OutputField(desc="研究手法の簡潔な説明")
    conclusion: str = dspy.OutputField(desc="結論と主要な発見")
    key_words: list[str] = dspy.OutputField(desc="キーワード (5-10 terms in English)")


class PaperSummarySections(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_SECTIONS_PROMPT)
    paper_text: str = dspy.InputField(desc="論文の全文テキスト")
    lang_name: str = dspy.InputField(desc="出力する言語")
    sections: list[dict] = dspy.OutputField(
        desc="セクションごとの要約リスト [{'section': '...', 'summary': '...'}]"
    )


class PaperSummaryContext(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_AI_CONTEXT_PROMPT)
    paper_text: str = dspy.InputField(desc="論文のテキスト")
    max_length: int = dspy.InputField(desc="最大文字数")
    summary: str = dspy.OutputField(desc="AIコンテキスト用の簡潔な要約")


# =============================================================
# Chat (対話系) の DSPy Signatures
# =============================================================


class ChatGeneral(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(CHAT_GENERAL_RESPONSE_PROMPT)
    document_context: str = dspy.InputField(desc="論文の文脈情報")
    history_text: str = dspy.InputField(desc="これまでの会話履歴")
    user_message: str = dspy.InputField(desc="ユーザーの質問")
    lang_name: str = dspy.InputField(desc="出力する言語")
    answer: str = dspy.OutputField(desc="質問への回答テキスト")


class ChatAuthorPersona(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(CHAT_AUTHOR_PERSONA_PROMPT)
    paper_text: str = dspy.InputField(desc="論文テキスト")
    question: str = dspy.InputField(desc="読者（ユーザー）の質問")
    lang_name: str = dspy.InputField(desc="出力する言語")
    author_answer: str = dspy.OutputField(desc="著者視点での回答テキスト")


# =============================================================
# Agent (分析・レビュー系) の DSPy Signatures
# =============================================================


class AdversarialCritique(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(AGENT_ADVERSARIAL_CRITIQUE_PROMPT)
    paper_text: str = dspy.InputField(desc="論文テキスト")
    lang_name: str = dspy.InputField(desc="出力言語")
    hidden_assumptions: list[dict] = dspy.OutputField(
        desc="隠れた前提とそのリスク [{'assumption': '...', 'risk': '...', 'severity': '...'}]"
    )
    unverified_conditions: list[dict] = dspy.OutputField(
        desc="未検証の条件とその影響 [{'condition': '...', 'impact': '...', 'severity': '...'}]"
    )
    reproducibility_risks: list[dict] = dspy.OutputField(
        desc="再現性に関するリスク [{'risk': '...', 'detail': '...', 'severity': '...'}]"
    )
    methodology_concerns: list[dict] = dspy.OutputField(
        desc="手法上の懸念と提案 [{'concern': '...', 'suggestion': '...', 'severity': '...'}]"
    )
    overall_assessment: str = dspy.OutputField(desc="全体的な批判的評価の要約")


# =============================================================
# Vision (図表分析系) の DSPy Signatures (※画像入力はGeminiマルチモーダル次第)
# =============================================================


class VisionAnalyzeFigure(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(VISION_ANALYZE_FIGURE_PROMPT)
    caption_hint: str = dspy.InputField(desc="図表のキャプション")
    lang_name: str = dspy.InputField(desc="出力言語")
    type_overview: str = dspy.OutputField(desc="図の概要と種類")
    key_findings: list[str] = dspy.OutputField(desc="主な傾向やパターン")
    interpretation: str = dspy.OutputField(desc="数値や傾向の解釈")
    implications: str = dspy.OutputField(desc="論文の主張に対する裏付け")
    highlights: list[str] = dspy.OutputField(desc="特筆すべき点や異常値")


# =============================================================
# 推薦機能 (Recommendation) の DSPy Signatures
# =============================================================


class PaperRecommendation(dspy.Signature):
    """
    ユーザーの知識レベルや興味、苦手な概念に基づいて、次に読むべき論文を推薦する。
    推薦論文は3件以上とし、Semantic Scholarでの検索用クエリを2件以上生成すること。
    初級ユーザーにはsurvey論文を含めることが望ましい。
    """

    paper_analysis: str = dspy.InputField(desc="現在の論文の解析結果")
    knowledge_level: str = dspy.InputField(desc="ユーザーの知識レベル")
    interests: str = dspy.InputField(desc="ユーザーの興味トピック")
    unknown_concepts: str = dspy.InputField(desc="ユーザーの苦手概念")
    preferred_direction: str = dspy.InputField(desc="推薦の方向性")
    recommendations: list[str] = dspy.OutputField(
        desc="推薦論文リスト（タイトル・理由含む）"
    )
    search_queries: list[str] = dspy.OutputField(desc="Semantic Scholar検索クエリ")
    reasoning: str = dspy.OutputField(desc="推薦理由の説明")


class UserProfileEstimation(dspy.Signature):
    """ユーザーの行動データから理解度・興味・苦手な概念を推定する。"""

    paper_summary: str = dspy.InputField(desc="論文要約")
    conversation_history: str = dspy.InputField(desc="対話履歴")
    word_clicks: str = dspy.InputField(desc="クリックされた単語一覧")
    knowledge_level: str = dspy.OutputField(desc="初級 / 中級 / 上級")
    interests: list[str] = dspy.OutputField(desc="興味トピック")
    unknown_concepts: list[str] = dspy.OutputField(desc="理解できていない概念")
    preferred_direction: str = dspy.OutputField(desc="深堀り / 横展開 / 応用 / 基礎")


# =============================================================
# Translation (翻訳系) の DSPy Signatures
# =============================================================


class ContextAwareTranslation(dspy.Signature):
    """
    You are an expert academic research assistant.
    Your goal is to help users understand complex academic papers, translate technical terms accurately within context.

    1. Always output ONLY in the requested target language.
    2. When translating, prioritize accuracy and academic context. Output the translation and an intuitive explanation that fits the context.
    3. NEVER mix languages in your response.
    """

    paper_context: str = dspy.InputField(desc="Context from the paper")
    target_text: str = dspy.InputField(desc="Text to translate")
    lang_name: str = dspy.InputField(desc="Target language")
    translation_and_explanation: str = dspy.OutputField(
        desc="Translation and context-aware explanation"
    )

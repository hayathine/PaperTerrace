import re

import dspy

from common.prompts import (
    AGENT_ADVERSARIAL_CRITIQUE_PROMPT,
    CHAT_GENERAL_RESPONSE_PROMPT,
    CORE_SYSTEM_PROMPT,
    DICT_EXPLAIN_GEMINI_PROMPT,
    DICT_TRANSLATE_QWEN_PROMPT,
    DICT_TRANSLATE_WORD_SIMPLE_PROMPT,
    PAPER_SUMMARY_FULL_PROMPT,
    PAPER_SUMMARY_SECTIONS_PROMPT,
    RECOMMENDATION_PAPER_PROMPT,
    RECOMMENDATION_USER_PROFILE_PROMPT,
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
    # DSPyのInputField名（input_data, lang_name, user_persona）に統一・置換する
    # これにより、プロンプト内でモデルがどのフィールドを参照すべきか明確になる
    cleaned = cleaned.replace("PAPER_TEXT: {paper_text}", "")
    cleaned = cleaned.replace("{paper_text}", "`input_data`")
    cleaned = cleaned.replace("{text}", "`input_data`")
    cleaned = cleaned.replace("{input_data}", "`input_data`")
    cleaned = cleaned.replace("{lang_name}", "`lang_name`")
    cleaned = cleaned.replace("{user_persona}", "`user_persona`")

    cleaned = cleaned.replace("{document_context}", "the academic paper context")
    cleaned = cleaned.replace("{history_text}", "the conversation history")
    cleaned = cleaned.replace("{question}", "the user's question (`input_data`)")
    cleaned = cleaned.replace("{caption_hint}", "[`input_data`]")
    cleaned = cleaned.replace("{context_hint}", "the context hint")
    cleaned = cleaned.replace("{table_text}", "the table text")
    cleaned = cleaned.replace("{paragraph}", "the paragraph text")
    cleaned = cleaned.replace("{target_word}", "`input_data`")
    cleaned = cleaned.replace("{trajectory}", "the user's trajectory")
    cleaned = cleaned.replace("{paper_analysis}", "`input_data`")
    cleaned = cleaned.replace("{summary_context}", "the paper summary context")
    cleaned = cleaned.replace("{context}", "the surrounding context")

    # paper_context は InputField 名と一致させることでモデルの参照を助ける
    cleaned = cleaned.replace(
        "{paper_context}",
        "the academic paper context provided in the `paper_context` field",
    )

    cleaned = cleaned.replace("context above", "provided context")
    cleaned = cleaned.replace(
        "Based on the context above", "Based on the provided context"
    )

    # DSPyは自身の構造化出力フォーマット（フィールドマーカー）を使用するため、
    # プロンプト内のJSON出力形式の指示を除去する。
    cleaned = re.sub(
        r"Please output in the following JSON format.*?Output ONLY valid JSON\.",
        "Output each field according to the instructions.",
        cleaned,
        flags=re.DOTALL,
    )

    # Core Promptを結合して、安定した品質のベースラインとする
    return f"{CORE_SYSTEM_PROMPT}\n\n[Task Instructions]\n{cleaned}".strip()


# =============================================================
# Behavioral Analysis & Personalized Response Signatures
# =============================================================


class ExtractUserTraits(dspy.Signature):
    behavior_logs = dspy.InputField()

    interests = dspy.OutputField()
    expertise_level = dspy.OutputField()
    explanation_preference = dspy.OutputField()
    key_words = dspy.OutputField()
    stress_level = dspy.OutputField(desc="The user's stress level")


class BuildDecisionProfile(dspy.Signature):
    current_logs = dspy.InputField(desc="The user's current behavior logs")
    user_feedback = dspy.InputField(desc="The user's feedback")
    interests = dspy.InputField(desc="The user's interests")
    expertise_level = dspy.InputField(desc="The user's expertise level")
    explanation_preference = dspy.InputField(desc="The user's explanation preference")
    key_words = dspy.InputField(desc="The user's key words")
    stress_level = dspy.InputField(desc="The user's stress level")

    user_persona = dspy.OutputField(desc="The user's persona")


class SolveTask(dspy.Signature):
    user_persona = dspy.InputField(desc="The user's persona")
    lang_name = dspy.InputField()
    input_data = dspy.InputField()


# =============================================================
# Summary (要約系) の DSPy Signatures
# =============================================================


class PaperSummary(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_FULL_PROMPT)
    overview: str = dspy.OutputField(
        desc="Overview and high-level summary (1-2 sentences)"
    )
    key_contributions: list[str] = dspy.OutputField(
        desc="Main contributions and novel points (3-5 items)"
    )
    methodology: str = dspy.OutputField(
        desc="Concise explanation of research methodology"
    )
    conclusion: str = dspy.OutputField(desc="Conclusion and key findings")
    key_words: list[str] = dspy.OutputField(desc="Keywords (5-10 terms in English)")


class PaperSummarySections(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_SECTIONS_PROMPT)
    sections: list[dict] = dspy.OutputField(
        desc="Section-by-section summary list [{'section': '...', 'summary': '...'}]"
    )


class PaperSummaryContext(dspy.Signature):
    """Generate a brief summary of the paper for AI context."""

    input_data = dspy.InputField(desc="Segment of the paper text")
    max_length = dspy.InputField(desc="Maximum number of characters for the summary")
    summary = dspy.OutputField(desc="Brief summary text")


# =============================================================
# Chat (対話系) の DSPy Signatures
# =============================================================


class ChatGeneral(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(CHAT_GENERAL_RESPONSE_PROMPT)
    document_context: str = dspy.InputField(
        desc="Contextual information from the paper"
    )
    history_text: str = dspy.InputField(desc="Previous conversation history")
    answer: str = dspy.OutputField(desc="Text of the answer to the question")


# =============================================================
# Agent (分析・レビュー系) の DSPy Signatures
# =============================================================


class AdversarialCritique(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(AGENT_ADVERSARIAL_CRITIQUE_PROMPT)
    hidden_assumptions: list[dict] = dspy.OutputField(
        desc="Hidden assumptions and their risks [{'assumption': '...', 'risk': '...', 'severity': '...'}]"
    )
    unverified_conditions: list[dict] = dspy.OutputField(
        desc="Unverified conditions and their impacts [{'condition': '...', 'impact': '...', 'severity': '...'}]"
    )
    reproducibility_risks: list[dict] = dspy.OutputField(
        desc="Risks related to reproducibility [{'risk': '...', 'detail': '...', 'severity': '...'}]"
    )
    methodology_concerns: list[dict] = dspy.OutputField(
        desc="Methodological concerns and suggestions [{'concern': '...', 'suggestion': '...', 'severity': '...'}]"
    )
    overall_assessment: str = dspy.OutputField(
        desc="Summary of the overall critical assessment"
    )


# =============================================================
# Vision (図表分析系) の DSPy Signatures (※画像入力はGeminiマルチモーダル次第)
# =============================================================


class VisionAnalyzeFigure(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(VISION_ANALYZE_FIGURE_PROMPT)
    type_overview: str = dspy.OutputField(desc="Overview and type of the figure")
    key_findings: list[str] = dspy.OutputField(desc="Main trends or patterns")
    interpretation: str = dspy.OutputField(desc="Interpretation of data or trends")
    implications: str = dspy.OutputField(desc="Support for the paper's claims")
    highlights: list[str] = dspy.OutputField(desc="Notable points or anomalies")


# =============================================================
# 推薦機能 (Recommendation) の DSPy Signatures
# =============================================================


class PaperRecommendation(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(RECOMMENDATION_PAPER_PROMPT)
    recommendations: list[str] = dspy.OutputField(
        desc="List of recommended papers (including titles and reasons)"
    )
    search_queries: list[str] = dspy.OutputField(
        desc="Search queries for Semantic Scholar"
    )


class UserProfileEstimation(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(RECOMMENDATION_USER_PROFILE_PROMPT)

    paper_summary: str = dspy.InputField(desc="Summary of the paper")
    conversation_history: str = dspy.InputField(desc="Conversation history")
    word_clicks: str = dspy.InputField(desc="List of words clicked by the user")
    knowledge_level: str = dspy.OutputField(desc="Beginner / Intermediate / Advanced")
    interests: list[str] = dspy.OutputField(desc="Interesting topics")
    unknown_concepts: list[str] = dspy.OutputField(desc="Concepts not yet understood")
    preferred_direction: str = dspy.OutputField(
        desc="Deep dive / Broadening / Application / Fundamentals"
    )


# =============================================================
# Translation (翻訳系) の DSPy Signatures
# =============================================================


class ContextAwareTranslation(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(DICT_TRANSLATE_QWEN_PROMPT)

    paper_context: str = dspy.InputField(
        desc="Academic paper context including surrounding sentences around the target word (paper summary and/or nearby text excerpt)"
    )
    translation_and_explanation: str = dspy.OutputField(
        desc="Concise translation based on context"
    )


class SimpleTranslation(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(DICT_TRANSLATE_WORD_SIMPLE_PROMPT)

    paper_context: str = dspy.InputField(desc="Academic context or summary")
    translation: str = dspy.OutputField(desc="Concise translation")


class DeepExplanation(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(DICT_EXPLAIN_GEMINI_PROMPT)

    summary_context: str = dspy.InputField(desc="Abstract or summary of the paper")
    context: str = dspy.InputField(desc="Surrounding text context")
    explanation: str = dspy.OutputField(desc="Concise context-aware explanation")

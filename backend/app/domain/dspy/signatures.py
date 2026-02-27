import dspy

from app.domain.prompts import (
    AGENT_ADVERSARIAL_CRITIQUE_PROMPT,
    AGENT_CITE_INTENT_PROMPT,
    CHAT_AUTHOR_PERSONA_PROMPT,
    CHAT_GENERAL_RESPONSE_PROMPT,
    CORE_SYSTEM_PROMPT,
    PAPER_SUMMARY_ABSTRACT_PROMPT,
    PAPER_SUMMARY_FULL_PROMPT,
    PAPER_SUMMARY_SECTIONS_PROMPT,
    VISION_ANALYZE_FIGURE_PROMPT,
    VISION_ANALYZE_TABLE_PROMPT,
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


class PaperAnalysis(dspy.Signature):
    """論文を構造化して解析する"""

    paper_text: str = dspy.InputField(desc="論文全文テキスト")
    title: str = dspy.OutputField(desc="論文タイトル")
    summary: str = dspy.OutputField(desc="要約（300字程度）")
    keywords: list[str] = dspy.OutputField(desc="キーワード一覧")
    difficulty: str = dspy.OutputField(desc="初級 / 中級 / 上級")
    contributions: str = dspy.OutputField(desc="主な貢献・新規性")
    related_fields: list[str] = dspy.OutputField(desc="関連する研究分野")


# =============================================================
# Summary (要約系) の DSPy Signatures
# =============================================================


class PaperSummary(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_FULL_PROMPT)
    paper_text: str = dspy.InputField(desc="論文の全文テキスト")
    lang_name: str = dspy.InputField(desc="出力する言語（例: Japanese）")
    summary: str = dspy.OutputField(desc="4つのセクションに分かれた指定言語での要約")


class PaperSummarySections(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_SECTIONS_PROMPT)
    paper_text: str = dspy.InputField(desc="論文の全文テキスト")
    lang_name: str = dspy.InputField(desc="出力する言語")
    sections_json: str = dspy.OutputField(desc="セクションごとの要約を格納したJSON")


class PaperSummaryAbstract(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(PAPER_SUMMARY_ABSTRACT_PROMPT)
    paper_text: str = dspy.InputField(desc="論文の全文テキスト")
    lang_name: str = dspy.InputField(desc="出力する言語")
    abstract: str = dspy.OutputField(desc="100-200語程度のアブストラクト要約")


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


class PaperQA(dspy.Signature):
    """論文の内容に基づいて質問に回答する"""

    paper_summary: str = dspy.InputField(desc="論文要約")
    question: str = dspy.InputField(desc="ユーザーの質問")
    conversation_history: str = dspy.InputField(desc="対話履歴")
    answer: str = dspy.OutputField(desc="回答テキスト")
    follow_up: str = dspy.OutputField(desc="次におすすめの質問")


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
    critique_json: str = dspy.OutputField(desc="JSONフォーマットの批判的レビュー結果")


class CiteIntentAnalysis(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(AGENT_CITE_INTENT_PROMPT)
    paragraph: str = dspy.InputField(desc="引用を含むパラグラフ")
    lang_name: str = dspy.InputField(desc="出力言語")
    intent_analysis: str = dspy.OutputField(desc="引用意図の分類と理由")


# =============================================================
# Vision (図表分析系) の DSPy Signatures (※画像入力はGeminiマルチモーダル次第)
# =============================================================


class VisionAnalyzeFigure(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(VISION_ANALYZE_FIGURE_PROMPT)
    caption_hint: str = dspy.InputField(desc="図表のキャプション")
    # 画像等の入力を dspy で扱う場合、マルチモーダルサポートか、文字起こしをベースにする
    lang_name: str = dspy.InputField(desc="出力言語")
    figure_analysis: str = dspy.OutputField(desc="図表の詳細分析")


class VisionAnalyzeTable(dspy.Signature):
    __doc__ = clean_prompt_for_dspy(VISION_ANALYZE_TABLE_PROMPT)
    context_hint: str = dspy.InputField(desc="周辺文脈")
    table_text: str = dspy.InputField(desc="抽出された表のテキスト情報")
    lang_name: str = dspy.InputField(desc="出力言語")
    table_analysis: str = dspy.OutputField(desc="表の詳細分析")


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


class RecommendationCritique(dspy.Signature):
    """推薦結果を批判的に吟味し、改善案を提示する"""

    user_profile: str = dspy.InputField(desc="ユーザープロファイル情報")
    recommendations: str = dspy.InputField(desc="現在の推薦論文リスト")
    critique: str = dspy.OutputField(desc="批判的な分析結果")
    improved_recommendations: list[str] = dspy.OutputField(
        desc="改善された推薦論文リスト"
    )


class UserProfileEstimation(dspy.Signature):
    """ユーザーの行動データから理解度・興味・苦手な概念を推定する。"""

    paper_summary: str = dspy.InputField(desc="論文要約")
    conversation_history: str = dspy.InputField(desc="対話履歴")
    word_clicks: str = dspy.InputField(desc="クリックされた単語一覧")
    knowledge_level: str = dspy.OutputField(desc="初級 / 中級 / 上級")
    interests: list[str] = dspy.OutputField(desc="興味トピック")
    unknown_concepts: list[str] = dspy.OutputField(desc="理解できていない概念")
    preferred_direction: str = dspy.OutputField(desc="深堀り / 横展開 / 応用 / 基礎")

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WordClickEvent:
    word: str  # クリックした単語
    context: str  # 前後の文脈（前後50文字程度）
    section: str  # Abstract / Introduction / Method / Results / Other
    timestamp: float  # クリック時刻（UNIXタイムスタンプ）


@dataclass
class TrajectoryRecord:
    user_id: str  # ユーザー識別子
    session_id: str  # セッション識別子
    timestamp: str  # 記録日時（ISO形式）
    paper_id: str  # 論文識別子（タイトルのハッシュ等）
    paper_title: str  # 論文タイトル
    paper_abstract: str  # 論文アブストラクト
    paper_keywords: list[str]  # 論文のキーワード
    paper_difficulty: str  # 論文の難易度（初級/中級/上級）
    recommended_papers: list[str]  # 推薦された論文タイトル一覧
    conversation_history: str  # 対話全文
    word_clicks: list[WordClickEvent]  # 翻訳クリックイベント
    clicked_papers: list[str]  # クリックされた推薦論文タイトル
    followed_up_query: bool  # 推薦後に追加質問したか
    session_duration: float  # セッション時間（秒）
    user_score: Optional[int] = None  # ユーザーの10段階評価（後追い更新）
    user_comment: Optional[str] = None  # テキストコメント（後追い更新）
    knowledge_level: str = ""  # 推定された知識レベル
    interests: list[str] = field(default_factory=list)  # 推定された興味
    unknown_concepts: list[str] = field(default_factory=list)  # 推定された苦手概念


@dataclass
class ChatTrajectoryRecord:
    user_id: str
    session_id: str
    timestamp: str
    paper_id: str
    user_message: str
    bot_response: str
    conversation_history: str
    user_score: Optional[int] = None
    user_comment: Optional[str] = None
    clicked_suggested_questions: bool = False
    session_duration: float = 0.0


@dataclass
class CriticTrajectoryRecord:
    user_id: str
    session_id: str
    timestamp: str
    target_module: str  # e.g., 'recommendation', 'chat'
    original_output: str
    critique_result: str
    improved_output: str
    human_accepted: bool = False


@dataclass
class TranslationTrajectoryRecord:
    user_id: str
    session_id: str
    timestamp: str
    paper_id: str
    original_word: str
    context: str
    translation: str
    model_used: str  # gemini, qwen, m2m100, etc.
    user_score: Optional[int] = None  # User rating for the translation
    user_saved_to_notes: bool = (
        False  # Implicit feedback: saving to notes means it was useful
    )
    prompt_length: int = (
        0  # To track and penalize long prompts during DSPy optimization
    )


def extract_text_feedback(example) -> Optional[str]:
    """GEPA用のテキストフィードバック生成ロジック"""
    feedback = getattr(example, "feedback", None)
    if not feedback:
        return None

    parts = []

    if getattr(feedback, "user_comment", None):
        parts.append(f"ユーザーコメント: {feedback.user_comment}")

    if getattr(feedback, "user_score", None) is not None:
        if feedback.user_score <= 3:
            parts.append("評価が非常に低い（3/10以下）: 推薦が全く的外れだった可能性")
        elif feedback.user_score <= 6:
            parts.append(f"評価がやや低い（{feedback.user_score}/10）: 改善の余地あり")
        elif feedback.user_score >= 9:
            parts.append(
                f"評価が非常に高い（{feedback.user_score}/10）: このパターンを維持すべき"
            )

    if getattr(feedback, "word_clicks", None) is not None:
        click_count = len(feedback.word_clicks)
        if click_count > 5:
            concepts = [w.word for w in feedback.word_clicks[:5]]
            parts.append(
                f"専門用語クリックが多い（{', '.join(concepts)}）: 論文が難しすぎた可能性"
            )
        elif click_count == 0:
            parts.append("単語クリックなし: 論文の難易度は適切だった")

    if not getattr(feedback, "clicked_papers", None):
        parts.append("推薦論文がクリックされなかった: 興味を引けなかった")
    else:
        parts.append(
            f"クリックされた論文: {feedback.clicked_papers}: このタイプが好まれた"
        )

    if getattr(feedback, "followed_up_query", False):
        parts.append("推薦後に追加質問あり: 推薦が次の興味を引き出した")

    return "\n".join(parts) if parts else None


def extract_chat_text_feedback(example) -> Optional[str]:
    """GEPA用のChatフィードバック生成ロジック"""
    feedback = getattr(example, "feedback", None)
    if not feedback:
        return None

    parts = []
    if getattr(feedback, "user_comment", None):
        parts.append(f"ユーザーコメント: {feedback.user_comment}")

    if getattr(feedback, "user_score", None) is not None:
        if feedback.user_score <= 3:
            parts.append("評価が低い: 回答が不適切だった可能性")
        elif feedback.user_score >= 9:
            parts.append("評価が高い: 非常に有益な回答")

    if getattr(feedback, "clicked_suggested_questions", False):
        parts.append("提案された質問がクリックされた: 良い誘導だった")

    return "\n".join(parts) if parts else None


def extract_critic_text_feedback(example) -> Optional[str]:
    """GEPA用のCriticフィードバック生成ロジック"""
    feedback = getattr(example, "feedback", None)
    if not feedback:
        return None

    if getattr(feedback, "human_accepted", False):
        return "人間によって改善案が採用された: 非常に優れたCritic"
    return "改善案が採用されなかった: 指摘がずれていた可能性"


def extract_translation_text_feedback(example) -> Optional[str]:
    """GEPA用のTranslationフィードバック生成ロジック"""
    feedback = getattr(example, "feedback", None)
    if not feedback:
        return None

    parts = []
    if getattr(feedback, "user_score", None) is not None:
        if feedback.user_score <= 3:
            parts.append("評価が低い: 翻訳精度または文脈理解に課題あり")
        elif feedback.user_score >= 9:
            parts.append("評価が高い: 文句なしの翻訳")

    if getattr(feedback, "user_saved_to_notes", False):
        parts.append("ユーザーがノートに保存した: 実用的で価値のある翻訳だった")

    return "\n".join(parts) if parts else None

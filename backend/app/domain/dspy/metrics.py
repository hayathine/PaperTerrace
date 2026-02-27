from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecommendationFeedback:
    example_id: str
    user_score: Optional[int] = None  # 1〜10（ユーザーの10段階評価）
    user_comment: Optional[str] = None  # テキストコメント（GEPAに活用）
    clicked_papers: list[str] = field(default_factory=list)  # クリックされた推薦論文
    followed_up_query: bool = False  # 推薦後に追加質問したか
    word_clicks: list = field(default_factory=list)  # 翻訳クリックイベント


def recommendation_metric(example, prediction, trace=None) -> float:
    feedback: Optional[RecommendationFeedback] = getattr(example, "feedback", None)

    if feedback and feedback.user_score is not None:
        return _score_with_feedback(feedback, prediction)

    return _score_without_feedback(example, prediction)


def _score_with_feedback(feedback: RecommendationFeedback, prediction) -> float:
    """ユーザーの10段階評価をベースにスコアを計算"""
    # 10段階 → 0.0〜1.0 に正規化
    base_score = (feedback.user_score - 1) / 9.0

    bonus = 0.0
    if feedback.clicked_papers:
        bonus += 0.40  # 推薦論文をクリックした
    if feedback.followed_up_query:
        bonus += 0.35  # 推薦後に追加質問した

    return min(1.0, base_score + bonus)


def _score_without_feedback(example, prediction) -> float:
    """フィードバックなし → 行動データのみで評価"""
    feedback: Optional[RecommendationFeedback] = getattr(example, "feedback", None)

    if feedback is None:
        return 0.5  # ニュートラル

    bonus = 0.0
    if feedback.clicked_papers:
        bonus += 0.40
    if feedback.followed_up_query:
        bonus += 0.35

    return min(1.0, max(0.0, bonus))


@dataclass
class ChatFeedback:
    example_id: str
    user_score: Optional[int] = None
    user_comment: Optional[str] = None
    clicked_suggested_questions: bool = False
    session_duration: float = 0.0


def chat_metric(example, prediction, trace=None) -> float:
    feedback: Optional[ChatFeedback] = getattr(example, "feedback", None)
    if not feedback:
        return 0.5  # Neutral

    if feedback.user_score is not None:
        score = (feedback.user_score - 1) / 9.0
    else:
        score = 0.5

    if feedback.clicked_suggested_questions:
        score += 0.2

    # 滞在時間が長い場合は、対話が有効だったとみなす
    if feedback.session_duration > 120.0:
        score += 0.1

    return min(1.0, max(0.0, score))


@dataclass
class CriticFeedback:
    example_id: str
    human_accepted: bool = False


def critic_metric(example, prediction, trace=None) -> float:
    feedback: Optional[CriticFeedback] = getattr(example, "feedback", None)
    if not feedback:
        return 0.5

    return 1.0 if feedback.human_accepted else 0.0


@dataclass
class TranslationFeedback:
    example_id: str
    user_score: Optional[int] = None
    user_saved_to_notes: bool = False


def translation_metric(example, prediction, trace=None) -> float:
    feedback: Optional[TranslationFeedback] = getattr(example, "feedback", None)

    score = 0.5
    if feedback:
        if feedback.user_score is not None:
            score = (feedback.user_score - 1) / 9.0

        if feedback.user_saved_to_notes:
            score += 0.3

    score = min(1.0, max(0.0, score))

    # プロンプトの長さに対するペナルティ（LLMへの入力プロンプトが冗長になるのを防ぐ）
    prompt_len = 0
    if trace is not None and len(trace) > 0:
        # traceには実行時のステップ情報が含まれるため、そこから擬似的にプロンプト長を算出
        prompt_len = sum(len(str(step)) for step in trace)
    else:
        # traceがない場合は、example入力の長さで代用
        prompt_len = len(
            str(example.toDict() if hasattr(example, "toDict") else example)
        )

    # 1000文字ごとに0.02のペナルティを与える（最大0.2まで）
    penalty = min(0.2, (prompt_len / 1000.0) * 0.02)

    # スコアからペナルティを減算
    final_score = max(0.0, score - penalty)

    return final_score

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

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

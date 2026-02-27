from dataclasses import dataclass

from app.domain.features.recommendation.trajectory import TrajectoryRecord


@dataclass
class ContrastiveLearningRecord:
    """対照学習用データレコード（Cloud SQLに専用テーブルで保存）"""

    record_id: str
    user_id: str
    knowledge_level: str
    interests: list[str]
    unknown_concepts: list[str]
    preferred_direction: str
    conversation_history: str
    word_clicks_summary: str
    paper_title: str
    paper_abstract: str
    paper_keywords: list[str]
    paper_difficulty: str
    label: float
    label_weight: float
    label_source: str
    session_id: str
    created_at: str
    user_text: str = ""
    paper_text: str = ""


# Encoder logic removed for offline processing


def build_user_text(record: ContrastiveLearningRecord) -> str:
    """ユーザープロファイルをベクトル化用テキストに変換"""
    click_summary = record.word_clicks_summary or "クリックなし"
    return f"""
知識レベル: {record.knowledge_level}
興味トピック: {", ".join(record.interests)}
苦手概念: {", ".join(record.unknown_concepts)}
推薦方向: {record.preferred_direction}
翻訳クリック: {click_summary}
""".strip()


def build_paper_text(record: ContrastiveLearningRecord) -> str:
    """論文情報をベクトル化用テキストに変換"""
    return f"""
{record.paper_title}
{record.paper_abstract}
Keywords: {", ".join(record.paper_keywords)}
""".strip()


def generate_contrastive_records(
    record: TrajectoryRecord,
) -> list[ContrastiveLearningRecord]:
    """軌跡データから対照学習レコードを自動生成"""
    records = []

    for paper_title in record.recommended_papers:
        # 正例：クリックされた論文
        label_weight = 1.0
        label_source = "unknown"
        label = 0.0

        if paper_title in record.clicked_papers:
            weight = 1.0
            if record.user_score and record.user_score >= 8:
                weight = min(1.0, weight + 0.1)  # 高評価でさらに信頼度UP
            label, label_source, label_weight = 1.0, "clicked", weight

        # 正例（弱）：word_clicksが少ない（難易度が合っていた）
        elif (
            len(record.word_clicks) <= 2
            and record.user_score
            and record.user_score >= 7
        ):
            label, label_source, label_weight = 0.7, "low_word_clicks_high_score", 0.7

        # 負例：低評価
        elif record.user_score and record.user_score <= 3:
            label, label_source, label_weight = 0.0, "low_score", 0.9

        # 負例：クリックされなかった論文
        else:
            label, label_source, label_weight = 0.0, "not_clicked", 0.8

        # word_clicksの要約テキスト生成
        click_words = [w.word for w in record.word_clicks[:10]]
        word_clicks_summary = "、".join(click_words) if click_words else "なし"

        cl_record = ContrastiveLearningRecord(
            record_id=f"{record.session_id}_{hash(paper_title)}",
            session_id=record.session_id,
            user_id=record.user_id,
            knowledge_level=record.knowledge_level,
            interests=record.interests,
            unknown_concepts=record.unknown_concepts,
            preferred_direction=record.preferred_direction,
            conversation_history=record.conversation_history[-500:],  # 直近500文字
            word_clicks_summary=word_clicks_summary,
            paper_title=paper_title,
            paper_abstract="",  # 別途Semantic Scholar APIで補完
            paper_keywords=[],
            paper_difficulty=record.paper_difficulty,
            label=label,
            label_weight=label_weight,
            label_source=label_source,
            created_at=str(record.timestamp),
        )

        cl_record.user_text = build_user_text(cl_record)
        cl_record.paper_text = build_paper_text(cl_record)

        records.append(cl_record)

    return records

"""
論文処理ステータスの共通ユーティリティ。

layout_status / summary_status / grobid_status の判定ロジックを一元管理する。
backend と inference-service の両方から参照可能。
"""

from dataclasses import dataclass

# ステータス定数
SUCCESS = "success"
FAILED = "failed"
SKIPPED = "skipped"
PROCESSING = "processing"

# これら以外は「未完了」とみなして再解析対象とする
# "processing" を含めることで、すでに処理中の論文に対して重複タスクが起動されるのを防ぐ
_TERMINAL_STATUSES: frozenset[str] = frozenset({SUCCESS, SKIPPED, PROCESSING})


def needs_reanalysis(status: str | None) -> bool:
    """ステータスが再解析を必要とするか判定する。

    None / "failed" の場合は True、"success" / "skipped" / "processing" の場合は False。
    """
    return status not in _TERMINAL_STATUSES


@dataclass(frozen=True)
class PaperAnalysisNeeds:
    """論文の未完了解析項目をまとめるデータクラス。

    Attributes:
        layout: layout_json が未取得かつ layout_status が未完了 → 実解析が必要
        layout_heal: layout_json は存在するが layout_status が未設定 → ステータス修復のみ
        summary: summary_status が未完了 → 要約タスクが必要
        grobid: grobid_status が未完了 → GROBID タスクが必要
    """

    layout: bool
    layout_heal: bool
    summary: bool
    grobid: bool

    @property
    def any(self) -> bool:
        """いずれかの処理が必要かどうかを返す。"""
        return self.layout or self.layout_heal or self.summary or self.grobid


def get_analysis_needs(paper: dict) -> PaperAnalysisNeeds:
    """論文の処理ステータスから再解析が必要な項目を返す。

    - layout_json が存在しない場合のみ layout 解析を再実行対象とする。
    - layout_json が存在するが layout_status が未完了の場合はステータス修復のみ行う。
    - summary / grobid はステータスが未完了なら常に再実行対象とする。
    """
    layout_status = paper.get("layout_status")
    has_layout_data = bool(paper.get("layout_json"))
    layout_pending = needs_reanalysis(layout_status)

    return PaperAnalysisNeeds(
        layout=layout_pending and not has_layout_data,
        layout_heal=layout_pending and has_layout_data,
        summary=needs_reanalysis(paper.get("summary_status")),
        grobid=needs_reanalysis(paper.get("grobid_status")),
    )

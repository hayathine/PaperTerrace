from pydantic import BaseModel

from .bbox import BBoxModel


class LayoutItem(BaseModel):
    """レイアウト要素"""

    bbox: BBoxModel
    class_name: str
    score: float


# PP-DocLayoutの標準ラベル
LABELS = {
    0: "Table",
    1: "Figure",
    2: "Picture",
    3: "Formula",
    4: "Chart",
    5: "Algorithm",
    # 互換性のためのエイリアス
    9: "Equation",
    10: "Figure",
}

LAYOUT_LABELS = list(set(LABELS.values()))

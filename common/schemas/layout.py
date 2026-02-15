from pydantic import BaseModel

from .bbox import BBoxModel


class LayoutItem(BaseModel):
    """レイアウト要素"""

    bbox: BBoxModel
    class_name: str
    score: float


# PP-DocLayoutの標準ラベル
LAYOUT_LABELS = [
    # "Text",
    # "Title",
    "Figure",
    "Figure caption",
    "Table",
    "Table caption",
    # "Header",
    # "Footer",
    # "Reference",
    "Equation",
]

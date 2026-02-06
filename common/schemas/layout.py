from typing import List

from pydantic import BaseModel


class BBox(BaseModel):
    """バウンディングボックス [x_min, y_min, x_max, y_max]"""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_list(cls, coord: List[float]) -> "BBox":
        if len(coord) != 4:
            raise ValueError("BBox coord must have 4 elements")
        return cls(
            x_min=coord[0],
            y_min=coord[1],
            x_max=coord[2],
            y_max=coord[3],
        )

    def to_list(self) -> List[float]:
        return [self.x_min, self.y_min, self.x_max, self.y_max]


class LayoutItem(BaseModel):
    """レイアウト要素"""

    bbox: BBox
    class_name: str
    score: float


# PP-DocLayoutの標準ラベル
LAYOUT_LABELS = [
    "Text",
    "Title",
    "Figure",
    "Figure caption",
    "Table",
    "Table caption",
    "Header",
    "Footer",
    "Reference",
    "Equation",
]

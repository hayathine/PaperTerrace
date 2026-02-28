from typing import List, Sequence

from pydantic import BaseModel, Field


class BBoxModel(BaseModel):
    """
    Bounding Box schema [x_min, y_min, x_max, y_max].
    Provides utility methods for conversion and common operations.
    """

    x_min: float = Field(..., description="Leftmost coordinate")
    y_min: float = Field(..., description="Topmost coordinate")
    x_max: float = Field(..., description="Rightmost coordinate")
    y_max: float = Field(..., description="Bottommost coordinate")

    @classmethod
    def from_list(cls, coords: Sequence[float]) -> "BBoxModel":
        """Create BBox from a list or sequence of 4 floats."""
        if len(coords) != 4:
            raise ValueError(f"BBox requires exactly 4 coordinates, got {len(coords)}")
        return cls(
            x_min=float(coords[0]),
            y_min=float(coords[1]),
            x_max=float(coords[2]),
            y_max=float(coords[3]),
        )

    def to_list(self) -> List[float]:
        """Convert BBox to a list [x_min, y_min, x_max, y_max]."""
        return [self.x_min, self.y_min, self.x_max, self.y_max]

    @property
    def width(self) -> float:
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(0.0, self.y_max - self.y_min)

    @property
    def area(self) -> float:
        return self.width * self.height

    def __getitem__(self, item):
        # Support index access (e.g., bbox[0]) for backward compatibility with list-style usage
        return self.to_list()[item]


class LayoutItem(BaseModel):
    """レイアウト要素"""

    bbox: BBoxModel
    class_name: str
    score: float


LABELS = {
    0: "Paragraph-title",
    1: "Picture",  # image
    2: "Text",
    3: "Number",
    4: "Abstract",
    5: "Content",
    6: "Figure-title",
    7: "Formula",
    8: "Table",
    9: "Table-title",
    10: "Reference",
    11: "Title",  # doc_title
    12: "Footnote",
    13: "Header",
    14: "Algorithm",
    15: "Footer",
    16: "Seal",
    17: "Chart-title",
    18: "Chart",
    19: "Formula-number",
    20: "Header-image",
    21: "Footer-image",
    22: "Aside-text",
}


LAYOUT_LABELS = list(set(LABELS.values()))

from typing import List

from pydantic import BaseModel, Field


class FigureBox(BaseModel):
    """
    Represents a bounding box for a detected figure, table, or equation.
    """

    label: str = Field(description="Type of item: figure, table, or equation")
    box_2d: List[float] = Field(description="[ymin, xmin, ymax, xmax] normalized coordinates 0-1")


class FigureDetectionResponse(BaseModel):
    """
    Response schema for figure detection.
    """

    figures: List[FigureBox] = Field(description="List of detected figures, tables, and equations")

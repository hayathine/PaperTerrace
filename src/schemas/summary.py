from typing import List

from pydantic import BaseModel, Field


class FullSummaryResponse(BaseModel):
    """
    Paper full summary model.
    """

    overview: str = Field(..., description="Abstract or overview of the main theme (1-2 sentences)")
    key_contributions: List[str] = Field(..., description="List of 3-5 key contributions")
    methodology: str = Field(..., description="Concise explanation of the methodology")
    conclusion: str = Field(..., description="Key findings and implications")

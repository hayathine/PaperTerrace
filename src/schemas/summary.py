from typing import List

from pydantic import BaseModel, Field


class SectionSummary(BaseModel):
    """
    Represents a summary for a specific section of the paper.
    """

    section: str = Field(description="Title of the section")
    summary: str = Field(description="Summary of the section content")


class SectionSummaryList(BaseModel):
    """
    List of section summaries.
    """

    sections: List[SectionSummary] = Field(description="List of section summaries")


class FullSummaryResponse(BaseModel):
    """
    Paper full summary model.
    """

    overview: str = Field(..., description="Abstract or overview of the main theme (1-2 sentences)")
    key_contributions: List[str] = Field(..., description="List of 3-5 key contributions")
    methodology: str = Field(..., description="Concise explanation of the methodology")
    conclusion: str = Field(..., description="Key findings and implications")

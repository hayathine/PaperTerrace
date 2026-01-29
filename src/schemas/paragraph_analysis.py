from typing import List, Literal

from pydantic import BaseModel, Field


class ParagraphExplanationResponse(BaseModel):
    """
    Paragraph explanation result model.
    """

    main_claim: str = Field(..., description="The core argument or content of this paragraph")
    background_knowledge: str = Field(
        ..., description="Prerequisites or technical terms needed to understand this"
    )
    logic_flow: str = Field(..., description="How the argument or logic is developed")
    key_points: List[str] = Field(..., description="Important implications or things to note")


class TermExplanation(BaseModel):
    """
    Technical term explanation model.
    """

    term: str = Field(..., description="The technical term")
    explanation: str = Field(..., description="Concise explanation of the term")
    importance: Literal["high", "medium", "low"] = Field(..., description="Importance level")


class TerminologyList(BaseModel):
    """
    List of technical terms with explanations.
    """

    terms: List[TermExplanation] = Field(
        ..., description="List of extracted technical terms", max_length=10
    )

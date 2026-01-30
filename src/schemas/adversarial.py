from typing import List, Literal

from pydantic import BaseModel


class HiddenAssumption(BaseModel):
    assumption: str
    risk: str
    severity: Literal["high", "medium", "low"]


class UnverifiedCondition(BaseModel):
    condition: str
    impact: str
    severity: Literal["high", "medium", "low"]


class ReproducibilityRisk(BaseModel):
    risk: str
    detail: str
    severity: Literal["high", "medium", "low"]


class MethodologyConcern(BaseModel):
    concern: str
    suggestion: str
    severity: Literal["high", "medium", "low"]


class AdversarialCritiqueResponse(BaseModel):
    """
    Structured response for adversarial critique of a paper.
    """

    hidden_assumptions: List[HiddenAssumption]
    unverified_conditions: List[UnverifiedCondition]
    reproducibility_risks: List[ReproducibilityRisk]
    methodology_concerns: List[MethodologyConcern]
    overall_assessment: str

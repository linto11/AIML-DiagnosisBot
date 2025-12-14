from typing import List, Optional
from pydantic import BaseModel, Field


class ConditionHypothesis(BaseModel):
    name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty_notes: Optional[str] = None
    reasoning: str


class AssessmentResponse(BaseModel):
    summary: str
    red_flags: List[str]
    possible_conditions: List[ConditionHypothesis]
    urgency: str  # "self-care" | "see a doctor soon" | "emergency"
    next_steps: List[str]
    recommended_specialists: List[str]

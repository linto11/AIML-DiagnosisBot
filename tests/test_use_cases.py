import json
import pytest

from src.application.use_cases import IntakeAssessmentUseCase
from src.application.schemas import AssessmentResponse
from src.domain.models import SymptomIntake


class DummyLLM:
    def generate_intake_assessment_json(self, messages):
        # Return minimal valid JSON for schema
        return json.dumps({
            "summary": "Test summary",
            "red_flags": [],
            "possible_conditions": [
                {"name": "Common cold", "confidence": 0.4, "uncertainty_notes": "Limited info", "reasoning": "Mild symptoms"}
            ],
            "urgency": "self-care",
            "next_steps": ["Hydration"],
            "recommended_specialists": ["General Practitioner"],
        })


class DummySearch:
    def search_specialists(self, specialty: str, location_query: str, limit: int = 5):
        return []


def test_assess_returns_assessment():
    usecase = IntakeAssessmentUseCase(llm=DummyLLM(), doctor_search=DummySearch())
    intake = SymptomIntake(chief_complaint="cough")
    assessment = usecase.assess(intake)
    assert isinstance(assessment, AssessmentResponse)
    assert assessment.summary == "Test summary"
    assert assessment.urgency in {"self-care", "see a doctor soon", "emergency"}

from typing import List, Protocol
from src.domain.models import DoctorResult


class DoctorSearchPort(Protocol):
    def search_specialists(self, specialty: str, location_query: str, limit: int = 5) -> List[DoctorResult]:
        ...


class LLMPort(Protocol):
    def generate_intake_assessment_json(self, messages: List[dict]) -> str:
        """
        Accepts chat-style messages and returns a JSON string with assessment.
        """
        ...

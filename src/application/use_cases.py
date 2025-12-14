import json
import logging
from typing import List, Optional

from pydantic import ValidationError

from src.application.schemas import AssessmentResponse
from src.application.ports import LLMPort, DoctorSearchPort
from src.domain.models import SymptomIntake
from src.domain.rules import evaluate_red_flags


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a careful virtual health assistant. You are not a doctor. "
    "Always provide a disclaimer that this is NOT medical advice or a diagnosis. "
    "Ask and reason about symptoms safely. Never claim certainty; use 'possible explanations'. "
    "Return a strict JSON object matching the schema provided."
)


def build_user_prompt(intake: SymptomIntake) -> str:
    lines = [
        "Chief complaint: " + str(intake.chief_complaint or "unknown"),
        "Duration: " + str(intake.duration or "unknown"),
        "Severity (0-10): " + str(intake.severity_scale if intake.severity_scale is not None else "unknown"),
        "Onset: " + str(intake.onset or "unknown"),
        "Fever: " + ("yes" if intake.fever else ("no" if intake.fever is False else "unknown")),
        "Pain scale (0-10): " + str(intake.pain_scale if intake.pain_scale is not None else "unknown"),
        "Triggers: " + ", ".join(intake.triggers) if intake.triggers else "Triggers: none",
        "Relevant history: " + ", ".join(intake.relevant_history) if intake.relevant_history else "Relevant history: none",
        "Meds: " + ", ".join(intake.meds) if intake.meds else "Meds: none",
        "Allergies: " + ", ".join(intake.allergies) if intake.allergies else "Allergies: none",
        f"Demographics: age={intake.demographics.age}, sex={intake.demographics.sex}, "
        f"child={intake.demographics.is_child}, pregnant={intake.demographics.is_pregnant}, "
        f"elderly={intake.demographics.is_elderly}, immunocompromised={intake.demographics.is_immunocompromised}",
        "Red flag responses: " + json.dumps(intake.red_flag_answers or {}),
    ]
    return "\n".join(lines)


def build_schema_instructions() -> str:
    return (
        "Return ONLY valid JSON with keys: "
        "summary (string), red_flags (array of strings), possible_conditions (array of objects), "
        "urgency (one of 'self-care', 'see a doctor soon', 'emergency'), next_steps (array of strings), "
        "recommended_specialists (array of strings).\n"
        "Each possible condition object MUST have: name (string), confidence (float 0-1), "
        "uncertainty_notes (string, optional), reasoning (string)."
    )


class IntakeAssessmentUseCase:
    def __init__(self, llm: LLMPort, doctor_search: Optional[DoctorSearchPort] = None):
        self.llm = llm
        self.doctor_search = doctor_search

    def assess(self, intake: SymptomIntake) -> AssessmentResponse:
        red_flags = evaluate_red_flags(intake)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_schema_instructions()},
            {"role": "user", "content": build_user_prompt(intake)},
        ]
        raw = self.llm.generate_intake_assessment_json(messages)

        try:
            data = json.loads(raw)
            assessment = AssessmentResponse(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Assessment JSON invalid: %s. Attempting repair.", e)
            # Single repair attempt
            repair_messages = messages + [
                {"role": "user", "content": "Repair: Return valid JSON only. No extra text."}
            ]
            raw = self.llm.generate_intake_assessment_json(repair_messages)
            data = json.loads(raw)
            assessment = AssessmentResponse(**data)

        # Override urgency if domain red flags indicate emergency
        if red_flags.emergency and assessment.urgency != "emergency":
            assessment.urgency = "emergency"
            assessment.red_flags = list(set(assessment.red_flags + red_flags.triggered))

        return assessment

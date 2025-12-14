from typing import List
from .models import SymptomIntake, RedFlagsResult


RED_FLAG_QUESTIONS = {
    "chest_pain": "Are you experiencing chest pain?",
    "difficulty_breathing": "Any difficulty breathing or shortness of breath?",
    "fainting": "Have you fainted or felt near-fainting?",
    "severe_bleeding": "Any severe or uncontrolled bleeding?",
    "stroke_signs": "Any signs of stroke (face drooping, arm weakness, speech difficulty)?",
    "suicidal_thoughts": "Any suicidal thoughts or intent?",
    "severe_abdominal_pain": "Severe abdominal pain?",
    "high_fever": "High fever (>39°C / 102°F)?",
}


def evaluate_red_flags(intake: SymptomIntake) -> RedFlagsResult:
    triggered: List[str] = []
    answers = intake.red_flag_answers or {}

    for key in RED_FLAG_QUESTIONS.keys():
        val = answers.get(key)
        if isinstance(val, str):
            val = val.strip().lower() in {"yes", "y", "true"}
        if val:
            triggered.append(key)

    # Adjust sensitivity for vulnerable populations
    demo = intake.demographics
    vulnerable = demo.is_child or demo.is_pregnant or demo.is_elderly or demo.is_immunocompromised

    emergency = "suicidal_thoughts" in triggered or "stroke_signs" in triggered or "severe_bleeding" in triggered
    if not emergency:
        # escalate to emergency if multiple severe flags or vulnerable
        severe_like = {"chest_pain", "difficulty_breathing", "fainting", "severe_abdominal_pain", "high_fever"}
        count_severe = sum(1 for t in triggered if t in severe_like)
        if count_severe >= 2 or (count_severe >= 1 and vulnerable):
            emergency = True

    return RedFlagsResult(triggered=triggered, emergency=emergency)

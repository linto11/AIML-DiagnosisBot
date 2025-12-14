import logging
import os
from typing import List

import streamlit as st

from src.infrastructure.config import Settings
from src.infrastructure.llm.mistral_client import MistralLLMAdapter
from src.infrastructure.doctor_search.google_places import GooglePlacesDoctorSearchAdapter
from src.infrastructure.doctor_search.mock_search import MockDoctorSearchAdapter
from src.application.use_cases import IntakeAssessmentUseCase
from src.domain.models import SymptomIntake, Demographics
from src.domain.rules import RED_FLAG_QUESTIONS


logger = logging.getLogger(__name__)


DISCLAIMER = (
    "This assistant is not a doctor. The information provided is "
    "for educational purposes only and is NOT medical advice or a diagnosis. "
    "If you experience emergency symptoms, seek immediate care (call local emergency number)."
)


def _init_adapters(settings: Settings):
    llm = MistralLLMAdapter(settings=settings)
    if settings.google_places_api_key:
        doctor_search = GooglePlacesDoctorSearchAdapter(settings=settings)
    else:
        doctor_search = MockDoctorSearchAdapter()
    return llm, doctor_search


def _ensure_session_state():
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "intake" not in st.session_state:
        st.session_state["intake"] = SymptomIntake()
    if "assessment" not in st.session_state:
        st.session_state["assessment"] = None


def _sidebar(settings: Settings):
    st.sidebar.title("Settings")
    st.sidebar.caption("LLM & Search")
    st.sidebar.write(f"Model: {settings.mistral_model}")

    # Location input for doctor search
    st.sidebar.text_input("Your city/area", key="location_query", placeholder="e.g., Dubai Marina")

    st.sidebar.checkbox("Opt-in: store chat locally (disabled by default)", key="store_chat", value=False)
    if st.sidebar.button("Reset chat"):
        st.session_state.clear()
        _ensure_session_state()
        st.experimental_rerun()


def _render_disclaimer():
    st.markdown(f"**Safety Notice:** {DISCLAIMER}")


def _require_mistral_key(settings: Settings) -> bool:
    if not settings.mistral_api_key:
        st.error(
            "Mistral API key missing. Add MISTRAL_API_KEY to .streamlit/secrets.toml or environment variables. "
            "See README for setup instructions."
        )
        return False
    return True


def _render_chat_history():
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])


def _ask_intake_questions(intake: SymptomIntake):
    # Chief complaint asked via chat input; follow-up targeted questions below.
    st.subheader("Symptom Intake")

    cols = st.columns(2)
    with cols[0]:
        intake.duration = st.text_input("Duration", value=intake.duration or "")
        intake.onset = st.text_input("Onset (sudden/gradual, when)", value=intake.onset or "")
        intake.severity_scale = st.slider("Severity (0-10)", 0, 10, value=intake.severity_scale or 5)
        intake.pain_scale = st.slider("Pain scale (0-10)", 0, 10, value=intake.pain_scale or 0)
        intake.fever = st.selectbox("Fever?", ["unknown", "no", "yes"], index=0 if intake.fever is None else (2 if intake.fever else 1))
        if isinstance(intake.fever, str):
            intake.fever = None if intake.fever == "unknown" else (intake.fever == "yes")
    with cols[1]:
        triggers = st.text_input("Triggers (comma separated)", value=", ".join(intake.triggers) if intake.triggers else "")
        intake.triggers = [t.strip() for t in triggers.split(",") if t.strip()] if triggers else []
        history = st.text_input("Relevant history (comma separated)", value=", ".join(intake.relevant_history) if intake.relevant_history else "")
        intake.relevant_history = [h.strip() for h in history.split(",") if h.strip()] if history else []
        meds = st.text_input("Medications (comma separated)", value=", ".join(intake.meds) if intake.meds else "")
        intake.meds = [m.strip() for m in meds.split(",") if m.strip()] if meds else []
        allergies = st.text_input("Allergies (comma separated)", value=", ".join(intake.allergies) if intake.allergies else "")
        intake.allergies = [a.strip() for a in allergies.split(",") if a.strip()] if allergies else []

    st.subheader("Demographics & Risk")
    d = intake.demographics or Demographics()
    d.age = st.number_input("Age", min_value=0, max_value=120, value=d.age or 30)
    d.sex = st.selectbox("Sex", ["unknown", "Male", "Female", "Other"], index=0 if not d.sex else ["unknown", "Male", "Female", "Other"].index(d.sex))
    d.is_child = st.checkbox("Child (<18)", value=d.is_child)
    d.is_pregnant = st.checkbox("Pregnant", value=d.is_pregnant)
    d.is_elderly = st.checkbox("Elderly (≥65)", value=d.is_elderly)
    d.is_immunocompromised = st.checkbox("Immunocompromised", value=d.is_immunocompromised)
    intake.demographics = d

    st.subheader("Red Flags")
    answers = intake.red_flag_answers or {}
    for key, question in RED_FLAG_QUESTIONS.items():
        current = answers.get(key, False)
        answers[key] = st.checkbox(question, value=current)
    intake.red_flag_answers = answers


def _render_assessment(assessment, doctor_results):
    st.subheader("Summary")
    st.write(assessment.summary)

    st.subheader("Red Flags Check")
    if assessment.red_flags:
        st.warning("Potential red flags: " + ", ".join(assessment.red_flags))
    else:
        st.success("No red flags reported.")

    st.subheader("Possible Conditions")
    for c in assessment.possible_conditions:
        st.write(f"- {c.name} (confidence: {c.confidence:.2f})")
        st.caption(f"Reasoning: {c.reasoning}")
        if c.uncertainty_notes:
            st.caption(f"Uncertainty: {c.uncertainty_notes}")

    st.subheader("Urgency Guidance")
    if assessment.urgency == "emergency":
        st.error("Emergency: seek immediate care (call local emergency number).")
    elif assessment.urgency == "see a doctor soon":
        st.warning("See a healthcare professional soon for evaluation.")
    else:
        st.info("Likely self-care is reasonable; monitor symptoms.")

    st.subheader("Recommended Next Steps")
    for step in assessment.next_steps:
        st.write(f"- {step}")

    st.subheader("Recommended Specialist(s)")
    if assessment.recommended_specialists:
        st.write(", ".join(assessment.recommended_specialists))
    else:
        st.write("None specified.")

    st.subheader("Local Doctors")
    if doctor_results:
        for d in doctor_results:
            st.write(f"**{d.name}** — {d.specialty or ''}")
            st.caption(f"Rating: {d.rating or 'N/A'}")
            if d.address:
                st.write(d.address)
            if d.phone:
                st.write(d.phone)
            if d.maps_url:
                st.link_button("Open in Maps", d.maps_url)
    else:
        st.caption("No local listings found or search disabled.")


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

    settings = Settings()
    if not _require_mistral_key(settings):
        _render_disclaimer()
        st.stop()

    _ensure_session_state()
    _sidebar(settings)
    _render_disclaimer()

    llm, doctor_search = _init_adapters(settings)
    usecase = IntakeAssessmentUseCase(llm=llm, doctor_search=doctor_search)

    st.title("Virtual Health Assistant (Safe & Structured)")

    _render_chat_history()

    prompt = st.chat_input("Describe your chief complaint (e.g., sore throat, headache)")
    intake: SymptomIntake = st.session_state["intake"]
    if prompt:
        intake.chief_complaint = prompt
        st.session_state["messages"].append({"role": "user", "content": prompt})

    _ask_intake_questions(intake)

    location = st.session_state.get("location_query") or ""
    if st.button("Analyze Symptoms"):
        try:
            assessment = usecase.assess(intake)

            st.session_state["assessment"] = assessment
            st.session_state["messages"].append({
                "role": "assistant",
                "content": "Analysis complete. See assessment sections below.",
            })

            # Doctor search if configured
            doctor_results = []
            if assessment.recommended_specialists:
                if isinstance(doctor_search, MockDoctorSearchAdapter) and not settings.google_places_api_key:
                    st.info("Local doctor search running in mock mode. Add GOOGLE_PLACES_API_KEY to enable real results.")
                if location:
                    for spec in assessment.recommended_specialists:
                        doctor_results.extend(doctor_search.search_specialists(spec, location, limit=5))
                else:
                    st.caption("Provide a city/area in the sidebar to search local doctors.")

            _render_assessment(assessment, doctor_results)

        except Exception as e:
            logger.exception("Assessment failed: %s", e)
            st.error("Something went wrong during assessment. Please try again.")

    # Show last assessment if present
    assessment = st.session_state.get("assessment")
    if assessment:
        # Recompute doctor results view on reload
        doctor_results = []
        if assessment.recommended_specialists and st.session_state.get("location_query"):
            for spec in assessment.recommended_specialists:
                doctor_results.extend(doctor_search.search_specialists(spec, st.session_state["location_query"], limit=5))
        _render_assessment(assessment, doctor_results)

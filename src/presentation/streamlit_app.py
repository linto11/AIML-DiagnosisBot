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
    st.subheader("📋 Assessment Results")
    
    # Summary card
    st.markdown("### Summary")
    st.info(assessment.summary)
    
    # Urgency badge (prominent)
    col_urgency = st.columns([1, 3])
    with col_urgency[0]:
        if assessment.urgency == "emergency":
            st.markdown("### ⚠️ EMERGENCY")
            st.error("Seek immediate medical care (call local emergency number)")
        elif assessment.urgency == "see a doctor soon":
            st.markdown("### ⏰ SOON")
            st.warning("Schedule a doctor appointment soon for professional evaluation")
        else:
            st.markdown("### ✅ SELF-CARE")
            st.success("Monitor symptoms; home care is likely appropriate")
    
    st.divider()
    
    # Red flags section
    st.markdown("### 🚨 Red Flags Check")
    if assessment.red_flags:
        for flag in assessment.red_flags:
            st.error(f"⚠️ {flag.replace('_', ' ').title()}")
    else:
        st.success("✓ No red flags detected")
    
    st.divider()
    
    # Possible conditions - Card layout
    st.markdown("### 🏥 Possible Conditions")
    if assessment.possible_conditions:
        cols = st.columns(min(len(assessment.possible_conditions), 2))
        for idx, condition in enumerate(assessment.possible_conditions):
            col_idx = idx % 2
            with cols[col_idx]:
                # Color based on confidence
                if condition.confidence >= 0.7:
                    color = "🟢"
                elif condition.confidence >= 0.5:
                    color = "🟡"
                else:
                    color = "🔵"
                
                with st.container(border=True):
                    st.markdown(f"#### {color} {condition.name}")
                    st.metric("Confidence", f"{condition.confidence * 100:.0f}%")
                    st.write(f"**Reasoning:** {condition.reasoning}")
                    if condition.uncertainty_notes:
                        st.caption(f"⚠️ *Uncertainty: {condition.uncertainty_notes}*")
    else:
        st.info("No conditions identified")
    
    st.divider()
    
    # Recommended next steps
    st.markdown("### 📝 Recommended Next Steps")
    if assessment.next_steps:
        for i, step in enumerate(assessment.next_steps, 1):
            st.write(f"{i}. {step}")
    else:
        st.write("No specific steps recommended")
    
    st.divider()
    
    # Specialists
    st.markdown("### 👨‍⚕️ Recommended Specialist(s)")
    if assessment.recommended_specialists:
        spec_cols = st.columns(len(assessment.recommended_specialists))
        for idx, spec in enumerate(assessment.recommended_specialists):
            with spec_cols[idx]:
                st.info(f"🏨 {spec}")
    else:
        st.write("No specialist recommended")
    
    st.divider()
    
    # Local doctors grid
    st.markdown("### 🗺️ Local Doctors & Specialists")
    if doctor_results:
        cols = st.columns(min(len(doctor_results), 2))
        for idx, doctor in enumerate(doctor_results):
            col_idx = idx % 2
            with cols[col_idx]:
                with st.container(border=True):
                    st.markdown(f"#### {doctor.name}")
                    if doctor.specialty:
                        st.caption(f"**{doctor.specialty}**")
                    
                    metrics_col1, metrics_col2 = st.columns(2)
                    with metrics_col1:
                        if doctor.rating:
                            st.metric("Rating", f"⭐ {doctor.rating:.1f}")
                    with metrics_col2:
                        st.metric("Status", "✓ Available")
                    
                    if doctor.address:
                        st.write(f"📍 {doctor.address}")
                    
                    if doctor.phone:
                        st.write(f"📞 {doctor.phone}")
                    
                    if doctor.maps_url:
                        st.link_button("🗺️ Open in Maps", doctor.maps_url, use_container_width=True)
    else:
        st.info("💡 No local listings found. Enter your city/area in the sidebar to search.")
    
    st.divider()
    st.caption("⚕️ **Disclaimer:** This assessment is NOT medical advice. Always consult a licensed healthcare professional.")


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

    settings = Settings()
    if not _require_mistral_key(settings):
        _render_disclaimer()
        st.stop()

    _ensure_session_state()
    _sidebar(settings)
    
    st.title("Virtual Health Assistant")
    _render_disclaimer()

    llm, doctor_search = _init_adapters(settings)
    usecase = IntakeAssessmentUseCase(llm=llm, doctor_search=doctor_search)

    # Main layout: tabs for chat vs form
    tab1, tab2, tab3 = st.tabs(["Chat", "Intake Form", "Results"])
    
    with tab1:
        st.subheader("Symptom Chat")
        
        # Display all previous messages
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        # Chat input
        prompt = st.chat_input("Describe your chief complaint (e.g., sore throat, headache)")
        if prompt:
            intake: SymptomIntake = st.session_state["intake"]
            intake.chief_complaint = prompt
            # Add user message
            st.session_state["messages"].append({"role": "user", "content": prompt})
            # Display it immediately
            with st.chat_message("user"):
                st.write(prompt)
            # Add a helper response
            st.session_state["messages"].append({
                "role": "assistant", 
                "content": f"Got it: {prompt}. Now fill in the details in the 'Intake Form' tab and click 'Analyze Symptoms'."
            })
            with st.chat_message("assistant"):
                st.write(f"Got it: {prompt}. Now fill in the details in the 'Intake Form' tab and click 'Analyze Symptoms'.")

    with tab2:
        st.subheader("Symptom Details")
        st.info("Fill in additional details about your symptoms.")
        intake: SymptomIntake = st.session_state["intake"]
        _ask_intake_questions(intake)
        
        location = st.session_state.get("location_query") or ""
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Analyze Symptoms", use_container_width=True):
                if not intake.chief_complaint:
                    st.error("Please enter a chief complaint in the Chat tab first.")
                else:
                    try:
                        with st.spinner("Analyzing symptoms with Mistral..."):
                            assessment = usecase.assess(intake)
                            st.session_state["assessment"] = assessment
                            st.session_state["messages"].append({
                                "role": "assistant",
                                "content": "Analysis complete. Check the Results tab.",
                            })
                            st.success("Analysis complete!")
                    except Exception as e:
                        logger.exception("Assessment failed: %s", e)
                        st.error(f"Assessment failed: {str(e)}")
        with col2:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.clear()
                _ensure_session_state()
                st.rerun()

    with tab3:
        st.subheader("Assessment Results")
        assessment = st.session_state.get("assessment")
        if not assessment:
            st.info("Complete the intake form and click 'Analyze Symptoms' to see results.")
        else:
            location = st.session_state.get("location_query") or ""
            doctor_results = []
            if assessment.recommended_specialists and location:
                for spec in assessment.recommended_specialists:
                    doctor_results.extend(doctor_search.search_specialists(spec, location, limit=5))
            elif assessment.recommended_specialists and not location:
                st.caption("Provide a city/area in the sidebar to search local doctors.")
            
            _render_assessment(assessment, doctor_results)

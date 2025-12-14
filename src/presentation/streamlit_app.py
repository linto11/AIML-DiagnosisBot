import logging
import os

import streamlit as st

from src.infrastructure.config import Settings
from src.infrastructure.llm.mistral_client import MistralLLMAdapter
from src.infrastructure.doctor_search.google_places import GooglePlacesDoctorSearchAdapter
from src.infrastructure.doctor_search.mock_search import MockDoctorSearchAdapter
from src.application.use_cases import IntakeAssessmentUseCase
from src.application.conversation import ConversationManager


logger = logging.getLogger(__name__)


DISCLAIMER = (
    "⚕️ **DISCLAIMER:** This is NOT medical advice and NOT a diagnosis. "
    "This chatbot is for educational purposes only. "
    "If you experience emergency symptoms, seek immediate care (call local emergency number)."
)


def _init_session_state():
    if "conversation" not in st.session_state:
        st.session_state.conversation = ConversationManager()
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "assessment_result" not in st.session_state:
        st.session_state.assessment_result = None


def _require_mistral_key(settings: Settings) -> bool:
    if not settings.mistral_api_key:
        st.error(
            "❌ **Mistral API Key Missing**\n\n"
            "Add `MISTRAL_API_KEY` to `.streamlit/secrets.toml` or as an environment variable.\n\n"
            "See README for setup instructions."
        )
        return False
    return True


def _render_sidebar(settings: Settings):
    st.sidebar.title("⚙️ Settings")
    
    st.sidebar.markdown("### Model")
    st.sidebar.caption(f"**Model:** {settings.mistral_model}")
    st.sidebar.caption(f"**API:** Mistral")
    
    st.sidebar.markdown("### Doctor Search")
    location = st.sidebar.text_input("Your city/area", placeholder="e.g., Dubai Marina")
    st.session_state["location_query"] = location
    
    if settings.google_places_api_key:
        st.sidebar.success("✓ Google Places API configured")
    else:
        st.sidebar.warning("⚠️ Google Places API not configured (using mock results)")
    
    st.sidebar.divider()
    
    if st.sidebar.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.conversation.start_new_conversation()
        st.session_state.chat_messages = []
        st.session_state.assessment_result = None
        st.rerun()


def _format_assessment_for_chat(assessment) -> str:
    """Format assessment as chat message."""
    lines = [
        "# 📋 Assessment Summary\n",
        f"**Summary:** {assessment.summary}\n",
    ]
    
    if assessment.urgency == "emergency":
        lines.append("## ⚠️ EMERGENCY")
        lines.append("**Seek immediate medical care by calling your local emergency number.**\n")
    elif assessment.urgency == "see a doctor soon":
        lines.append("## ⏰ See a Doctor Soon")
        lines.append("Schedule an appointment with a healthcare professional soon.\n")
    else:
        lines.append("## ✅ Self-Care Likely Appropriate")
        lines.append("Monitor your symptoms. Home care may be sufficient.\n")
    
    lines.append("## 🚨 Red Flags")
    if assessment.red_flags:
        for flag in assessment.red_flags:
            lines.append(f"- ⚠️ {flag.replace('_', ' ').title()}")
    else:
        lines.append("- ✓ No red flags detected")
    lines.append("")
    
    lines.append("## 🏥 Possible Conditions (NOT a diagnosis)")
    for condition in assessment.possible_conditions:
        confidence_pct = condition.confidence * 100
        icon = "🟢" if confidence_pct >= 70 else ("🟡" if confidence_pct >= 50 else "🔵")
        lines.append(f"**{icon} {condition.name}** (Confidence: {confidence_pct:.0f}%)")
        lines.append(f"- Why: {condition.reasoning}")
        if condition.uncertainty_notes:
            lines.append(f"- Note: {condition.uncertainty_notes}")
    lines.append("")
    
    lines.append("## 📝 Recommended Next Steps")
    for i, step in enumerate(assessment.next_steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("")
    
    lines.append("## 👨‍⚕️ Recommended Specialist(s)")
    if assessment.recommended_specialists:
        lines.append(", ".join(assessment.recommended_specialists))
    else:
        lines.append("No specific specialist recommended")
    lines.append("")
    
    lines.append("---")
    lines.append("⚠️ **Reminder:** This is NOT medical advice. Always consult a licensed healthcare professional.")
    
    return "\n".join(lines)


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    
    st.set_page_config(
        page_title="Virtual Health Assistant",
        page_icon="⚕️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    settings = Settings()
    if not _require_mistral_key(settings):
        st.stop()
    
    _init_session_state()
    _render_sidebar(settings)
    
    st.markdown("# 🏥 Virtual Health Assistant")
    st.info(DISCLAIMER)
    
    llm = MistralLLMAdapter(settings=settings)
    doctor_search = GooglePlacesDoctorSearchAdapter(settings=settings) if settings.google_places_api_key else MockDoctorSearchAdapter()
    usecase = IntakeAssessmentUseCase(llm=llm, doctor_search=doctor_search)
    
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    st.divider()
    
    conversation = st.session_state.conversation
    
    if conversation.is_ready_for_assessment() and st.session_state.assessment_result is None:
        with st.spinner("🔬 Analyzing your symptoms with AI..."):
            try:
                assessment = usecase.assess(conversation.intake)
                st.session_state.assessment_result = assessment
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": _format_assessment_for_chat(assessment),
                })
            except Exception as e:
                logger.exception("Assessment failed: %s", e)
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": f"❌ **Error during analysis:** {str(e)}\n\nPlease try again.",
                })
    
    user_input = st.chat_input("Type your response...")
    
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        conversation.process_user_response(user_input)
        
        if not conversation.is_ready_for_assessment():
            next_question = conversation.get_next_question()
            st.session_state.chat_messages.append({"role": "assistant", "content": next_question})
        
        st.rerun()
    
    if not st.session_state.chat_messages:
        first_question = conversation.get_next_question()
        st.session_state.chat_messages.append({"role": "assistant", "content": first_question})
        st.rerun()

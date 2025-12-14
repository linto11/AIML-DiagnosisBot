import logging
import os

import streamlit as st

from src.infrastructure.config import Settings
from src.infrastructure.llm.mistral_client import MistralLLMAdapter
from src.infrastructure.doctor_search.google_places import GooglePlacesDoctorSearchAdapter
from src.infrastructure.doctor_search.mock_search import MockDoctorSearchAdapter
from src.application.use_cases import IntakeAssessmentUseCase
from src.application.conversation import SmartConversationManager


logger = logging.getLogger(__name__)


DISCLAIMER = (
    "⚕️ **DISCLAIMER:** This is NOT medical advice and NOT a diagnosis. "
    "This chatbot is for educational purposes only. "
    "If you experience emergency symptoms, seek immediate care (call local emergency number)."
)


def _init_session_state(llm):
    if "smart_conversation" not in st.session_state:
        st.session_state.smart_conversation = SmartConversationManager(llm)
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "assessment_result" not in st.session_state:
        st.session_state.assessment_result = None
    if "doctors" not in st.session_state:
        st.session_state.doctors = []


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
    
    st.sidebar.markdown("### Doctor Search")
    location = st.sidebar.text_input("Your city/area", placeholder="e.g., Dubai Marina")
    st.session_state["location_query"] = location
    
    if settings.google_places_api_key:
        st.sidebar.success("✓ Google Places API configured")
    else:
        st.sidebar.warning("⚠️ Using mock doctor results")
    
    st.sidebar.divider()
    
    if st.sidebar.button("🔄 New Conversation", use_container_width=True):
        st.session_state.smart_conversation.start_new()
        st.session_state.chat_messages = []
        st.session_state.assessment_result = None
        st.session_state.doctors = []
        st.rerun()


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    
    st.set_page_config(
        page_title="Virtual Health Assistant",
        page_icon="⚕️",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    
    # Custom CSS for ChatGPT-style layout with proper left/right alignment
    st.markdown("""
    <style>
    /* Center chat container */
    [data-testid="stChatMessageContainer"] {
        max-width: 700px;
        margin: 0 auto;
    }
    
    .stChatMessage {
        max-width: 700px;
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        [data-testid="stChatMessageContainer"] {
            max-width: 100%;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    settings = Settings()
    if not _require_mistral_key(settings):
        st.stop()
    
    llm = MistralLLMAdapter(settings=settings)
    _init_session_state(llm)
    _render_sidebar(settings)
    
    # Header - centered
    st.markdown("# 🏥 Virtual Health Assistant", unsafe_allow_html=True)
    st.info(DISCLAIMER)
    
    # Chat container with max-width
    chat_container = st.container()
    
    with chat_container:
        # Display chat history
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Input area
    user_input = st.chat_input("Type your response...")
    
    if user_input:
        conversation = st.session_state.smart_conversation
        
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_input,
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Generate AI response
        with st.spinner("⏳ Thinking..."):
            ai_response = conversation.get_next_response(user_input)
        
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": ai_response,
        })
        
        # Check if assessment stage
        if conversation.stage == "assessment" and st.session_state.assessment_result is None:
            with st.spinner("🔬 Analyzing your condition..."):
                try:
                    usecase = IntakeAssessmentUseCase(llm=llm)
                    assessment = usecase.assess(conversation.intake)
                    st.session_state.assessment_result = assessment
                    
                    # Search for nearby doctors
                    location = st.session_state.get("location_query", "")
                    doctors = []
                    if assessment.recommended_specialists and location:
                        doctors = _search_doctors(settings, assessment.recommended_specialists, location)
                    st.session_state.doctors = doctors
                    
                    assessment_msg = _format_assessment_for_chat(assessment, doctors)
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": assessment_msg,
                    })
                except Exception as e:
                    logger.exception("Assessment failed: %s", e)
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": f"❌ **Error during analysis:** {str(e)}\n\nPlease try again.",
                    })
        
        st.rerun()
    
    # Initial message if no conversation yet
    if not st.session_state.chat_messages:
        first_msg = "Hi! I'm your virtual health assistant. What brings you in today? Please describe your main symptom or concern."
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": first_msg,
        })
        st.rerun()


def _format_assessment_for_chat(assessment, doctors=None) -> str:
    """Format assessment as chat message with discussion points and doctors."""
    lines = ["# 📋 Medical Assessment Report\n"]
    
    lines.append(f"**Summary:** {assessment.summary}\n")
    
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
    
    # ADD DISCUSSION POINTS FOR DOCTOR
    lines.append("## 💬 Key Discussion Points for Your Doctor")
    lines.append("When you visit your healthcare provider, consider discussing these points:")
    lines.append("")
    lines.append(f"- **Chief Complaint:** {assessment.summary}")
    lines.append(f"- **Ask about:** The conditions mentioned above")
    lines.append(f"- **Specialist to see:** {', '.join(assessment.recommended_specialists) if assessment.recommended_specialists else 'General Practitioner'}")
    if assessment.red_flags:
        lines.append(f"- **Important to mention:** The red flags detected in your symptoms")
    lines.append("- **Request:** Any tests or imaging that may be needed")
    lines.append("- **Ask about:** Treatment options and alternatives")
    lines.append("- **Discuss:** Expected timeline for recovery")
    lines.append("")
    
    # ADD NEARBY DOCTORS/CLINICS
    if doctors and len(doctors) > 0:
        lines.append("## 🏥 Nearby Clinics & Hospitals\n")
        for i, doctor in enumerate(doctors, 1):
            lines.append(f"### {i}. {doctor.get('name', 'Clinic')}")
            if doctor.get('rating'):
                lines.append(f"   ⭐ **Rating:** {doctor['rating']:.1f}/5")
            if doctor.get('address'):
                lines.append(f"   📍 **Address:** {doctor['address']}")
            if doctor.get('phone'):
                lines.append(f"   📞 **Phone:** `{doctor['phone']}`")
            if doctor.get('type'):
                lines.append(f"   🏢 **Type:** {doctor['type']}")
            if doctor.get('maps_url'):
                lines.append(f"   🗺️ [View on Google Maps]({doctor['maps_url']})")
            lines.append("")
    else:
        lines.append("## 🏥 Doctor Search\n")
        lines.append("To find nearby clinics and hospitals, please enter your city/area in the Settings sidebar.\n")
    
    lines.append("---")
    lines.append("⚠️ **Reminder:** This is NOT a diagnosis. Always consult a licensed healthcare professional for proper evaluation and treatment.")
    
    return "\n".join(lines)


def _search_doctors(settings: Settings, specialists: list, location: str) -> list:
    """Search for doctors/clinics based on specialists and location."""
    try:
        if settings.google_places_api_key:
            adapter = GooglePlacesDoctorSearchAdapter(
                api_key=settings.google_places_api_key
            )
            # Search for specialists
            query = specialists[0] if specialists else "clinic"
            doctors = adapter.search_specialists(f"{query} clinic in {location}")
        else:
            adapter = MockDoctorSearchAdapter()
            doctors = adapter.search_specialists(f"clinic in {location}")
        
        return doctors if doctors else []
    except Exception as e:
        logger.warning(f"Doctor search failed: {e}")
        # Return mock doctors as fallback
        try:
            mock_adapter = MockDoctorSearchAdapter()
            return mock_adapter.search_specialists(f"clinic in {location}")
        except Exception as e2:
            logger.error(f"Mock doctor search also failed: {e2}")
            return []


if __name__ == "__main__":
    main()

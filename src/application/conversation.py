import json
import logging
from enum import Enum
from typing import Optional, List

from src.domain.models import SymptomIntake, Demographics
from src.domain.rules import RED_FLAG_QUESTIONS, evaluate_red_flags
from src.application.ports import LLMPort


logger = logging.getLogger(__name__)


class SmartConversationManager:
    """Uses LLM to drive intelligent, adaptive medical intake conversations."""
    
    def __init__(self, llm: LLMPort):
        self.llm = llm
        self.intake = SymptomIntake()
        self.conversation_history: List[dict] = []
        self.stage = "initial"  # initial, intake, assessment
        self.questions_asked = 0
        self.max_questions = 15
        
    def start_new(self):
        self.intake = SymptomIntake()
        self.conversation_history = []
        self.stage = "initial"
        self.questions_asked = 0
    
    def get_next_response(self, user_message: str) -> str:
        """Get AI-generated response based on conversation context."""
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Determine what to do based on stage
        if self.stage == "initial":
            # First user message is chief complaint
            self.intake.chief_complaint = user_message
            self.stage = "intake"
            self.questions_asked = 1
            # Generate contextual follow-up question
            ai_response = self._generate_question()
        
        elif self.stage == "intake":
            # Update intake based on latest response
            self._update_intake_from_response(user_message)
            
            # Check if we have enough info
            if self.questions_asked >= self.max_questions or self._intake_complete():
                self.stage = "assessment"
                ai_response = "Let me confirm what I've learned and then provide an assessment.\n\n" + self._build_summary()
            else:
                # Generate next contextual question
                self.questions_asked += 1
                ai_response = self._generate_question()
        
        else:  # assessment stage
            ai_response = "Assessment complete. Please reset conversation to start again."
        
        # Add AI response to history
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        return ai_response
    
    def _generate_question(self) -> str:
        """Use LLM to generate the next contextual question."""
        context = self._build_conversation_context()
        
        prompt = f"""You are a medical intake assistant. Based on the conversation so far, ask ONE focused follow-up question to better understand the patient's condition.

CONVERSATION SO FAR:
{context}

CURRENT INTAKE DATA:
- Chief Complaint: {self.intake.chief_complaint}
- Duration: {self.intake.duration or 'Not asked'}
- Severity: {self.intake.severity_scale or 'Not asked'}/10
- Onset: {self.intake.onset or 'Not asked'}
- Fever: {self.intake.fever or 'Not asked'}
- Triggers: {', '.join(self.intake.triggers) if self.intake.triggers else 'Not asked'}
- Medical History: {', '.join(self.intake.relevant_history) if self.intake.relevant_history else 'Not asked'}
- Medications: {', '.join(self.intake.meds) if self.intake.meds else 'Not asked'}
- Allergies: {', '.join(self.intake.allergies) if self.intake.allergies else 'Not asked'}

GUIDELINES:
1. Ask ONE clear, focused question
2. Ask about missing important details (duration, severity, onset, triggers, history, meds, allergies)
3. Be conversational and empathetic
4. If patient seems confused, clarify your previous question
5. Check for red flags early (chest pain, breathing difficulty, fainting, severe bleeding, stroke signs)
6. Don't repeat questions already asked
7. Keep it brief (1-2 sentences)

Generate ONLY the question, no explanation."""
        
        messages = [
            {"role": "system", "content": "You are a caring medical intake assistant asking clarifying questions to understand a patient's condition."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm.generate_intake_assessment_json(messages)
            return response.strip()
        except Exception as e:
            logger.error("Failed to generate question: %s", e)
            # Fallback to simple questions
            return self._get_fallback_question()
    
    def _get_fallback_question(self) -> str:
        """Fallback simple question when LLM fails."""
        if not self.intake.duration:
            return "How long have you had this symptom?"
        if self.intake.severity_scale is None:
            return "On a scale of 0-10, how severe is this?"
        if not self.intake.onset:
            return "Did this start suddenly or gradually?"
        if self.intake.fever is None:
            return "Do you have a fever?"
        if not self.intake.triggers:
            return "Is there anything that makes it better or worse?"
        if not self.intake.relevant_history:
            return "Any relevant medical history (diabetes, heart disease, asthma, etc.)?"
        if not self.intake.meds:
            return "Are you taking any medications?"
        if not self.intake.allergies:
            return "Do you have any allergies?"
        if self.intake.demographics.age is None:
            return "What is your age?"
        return "Is there anything else important I should know?"
    
    def _update_intake_from_response(self, user_message: str) -> None:
        """Try to extract and update intake data from user response."""
        msg_lower = user_message.lower()
        
        # Try to detect if they mentioned duration
        if any(word in msg_lower for word in ["day", "week", "month", "hour", "since"]):
            if not self.intake.duration:
                self.intake.duration = user_message
        
        # Try to detect severity/pain scale
        if any(c.isdigit() for c in user_message):
            numbers = [int(s) for s in user_message.split() if s.isdigit()]
            if numbers and not self.intake.severity_scale and numbers[0] <= 10:
                self.intake.severity_scale = numbers[0]
            if numbers and self.intake.pain_scale is None and numbers[0] <= 10:
                self.intake.pain_scale = numbers[0]
        
        # Detect yes/no answers
        is_yes = msg_lower in {"yes", "y", "yep", "yeah", "true"}
        is_no = msg_lower in {"no", "n", "nope", "false"}
        
        if is_yes or is_no:
            # Try to match to most recent question
            if "fever" in self.conversation_history[-2]["content"].lower() if len(self.conversation_history) > 1 else False:
                self.intake.fever = is_yes
            elif "allerg" in self.conversation_history[-2]["content"].lower() if len(self.conversation_history) > 1 else False:
                if is_no and not self.intake.allergies:
                    self.intake.allergies = []
            elif "medic" in self.conversation_history[-2]["content"].lower() if len(self.conversation_history) > 1 else False:
                if is_no and not self.intake.meds:
                    self.intake.meds = []
    
    def _intake_complete(self) -> bool:
        """Check if we have essential info for assessment."""
        essential_filled = (
            self.intake.chief_complaint and
            self.intake.duration and
            (self.intake.severity_scale is not None)
        )
        return essential_filled
    
    def _build_conversation_context(self) -> str:
        """Build context from conversation history."""
        context_lines = []
        for msg in self.conversation_history[-6:]:  # Last 6 messages
            role = "Patient" if msg["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {msg['content']}")
        return "\n".join(context_lines) if context_lines else "No conversation yet"
    
    def _build_summary(self) -> str:
        """Build intake summary."""
        lines = ["## Summary of Your Symptoms\n"]
        
        if self.intake.chief_complaint:
            lines.append(f"**Chief Complaint:** {self.intake.chief_complaint}")
        if self.intake.duration:
            lines.append(f"**Duration:** {self.intake.duration}")
        if self.intake.severity_scale is not None:
            lines.append(f"**Severity:** {self.intake.severity_scale}/10")
        if self.intake.onset:
            lines.append(f"**Onset:** {self.intake.onset}")
        if self.intake.fever is not None:
            lines.append(f"**Fever:** {'Yes' if self.intake.fever else 'No'}")
        if self.intake.triggers:
            lines.append(f"**Triggers:** {', '.join(self.intake.triggers)}")
        if self.intake.relevant_history:
            lines.append(f"**Medical History:** {', '.join(self.intake.relevant_history)}")
        if self.intake.meds:
            lines.append(f"**Medications:** {', '.join(self.intake.meds)}")
        if self.intake.allergies:
            lines.append(f"**Allergies:** {', '.join(self.intake.allergies)}")
        
        lines.append("\nDoes this look correct?")
        return "\n".join(lines)


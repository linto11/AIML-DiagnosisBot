import json
import logging
from enum import Enum
from typing import Optional, List

from src.domain.models import SymptomIntake, Demographics
from src.domain.rules import RED_FLAG_QUESTIONS, evaluate_red_flags


logger = logging.getLogger(__name__)


class ConversationStage(Enum):
    INITIAL = "initial"  # Waiting for chief complaint
    CHIEF_COMPLAINT = "chief_complaint"  # Chief complaint received
    ASKING_FOLLOWUPS = "asking_followups"  # Asking about duration, severity, etc.
    RED_FLAG_CHECK = "red_flag_check"  # Asking red flag questions
    DEMOGRAPHICS = "demographics"  # Age, pregnancy, etc.
    SUMMARY = "summary"  # Confirming intake summary
    ASSESSMENT = "assessment"  # Generating final assessment
    RESULTS = "results"  # Showing results


class ConversationManager:
    """Manages the flow of a medical intake conversation."""
    
    def __init__(self):
        self.stage = ConversationStage.INITIAL
        self.intake = SymptomIntake()
        self.asked_questions: List[str] = []
        self.current_question_key: Optional[str] = None
        self.red_flags_checked = False
        
    def start_new_conversation(self):
        """Reset conversation to initial state."""
        self.stage = ConversationStage.INITIAL
        self.intake = SymptomIntake()
        self.asked_questions = []
        self.current_question_key = None
        self.red_flags_checked = False
    
    def get_next_question(self) -> str:
        """Determine and return the next question to ask based on stage and intake."""
        
        if self.stage == ConversationStage.INITIAL:
            return "What brings you in today? Please describe your main symptom or concern."
        
        elif self.stage == ConversationStage.CHIEF_COMPLAINT:
            # Ask about duration
            if "duration" not in self.asked_questions:
                self.current_question_key = "duration"
                return "How long have you had this symptom? (e.g., 2 days, 1 week)"
            
            # Ask about severity
            if "severity" not in self.asked_questions:
                self.current_question_key = "severity"
                return "On a scale of 0-10, how severe is this symptom? (0 = none, 10 = worst possible)"
            
            # Ask about onset
            if "onset" not in self.asked_questions:
                self.current_question_key = "onset"
                return "Did this start suddenly or gradually?"
            
            # Ask about fever (if relevant)
            if "fever" not in self.asked_questions:
                self.current_question_key = "fever"
                return "Do you have a fever?"
            
            # Ask about pain (if complaint mentions pain)
            if self._is_pain_related() and "pain" not in self.asked_questions:
                self.current_question_key = "pain"
                return "On a scale of 0-10, how would you rate the pain?"
            
            # Ask about triggers
            if "triggers" not in self.asked_questions:
                self.current_question_key = "triggers"
                return "Is there anything that makes it better or worse? (e.g., movement, position, food)"
            
            # Ask about history
            if "history" not in self.asked_questions:
                self.current_question_key = "history"
                return "Do you have any relevant medical history? (e.g., diabetes, heart disease, asthma)"
            
            # Ask about meds
            if "meds" not in self.asked_questions:
                self.current_question_key = "meds"
                return "Are you taking any medications?"
            
            # Ask about allergies
            if "allergies" not in self.asked_questions:
                self.current_question_key = "allergies"
                return "Do you have any known allergies?"
            
            # Move to red flags
            self.stage = ConversationStage.RED_FLAG_CHECK
            return self.get_next_question()
        
        elif self.stage == ConversationStage.RED_FLAG_CHECK:
            # Check red flags one by one
            for key, question in RED_FLAG_QUESTIONS.items():
                if key not in self.asked_questions:
                    self.current_question_key = key
                    return f"⚠️ Quick safety check: {question} (yes/no)"
            
            # Move to demographics
            self.stage = ConversationStage.DEMOGRAPHICS
            return self.get_next_question()
        
        elif self.stage == ConversationStage.DEMOGRAPHICS:
            # Ask age
            if "age" not in self.asked_questions:
                self.current_question_key = "age"
                return "How old are you?"
            
            # Ask about pregnancy if relevant
            if "pregnancy" not in self.asked_questions:
                self.current_question_key = "pregnancy"
                return "Are you pregnant or could you be pregnant?"
            
            # Ask about elderly
            if "elderly" not in self.asked_questions:
                self.current_question_key = "elderly"
                return "Are you 65 or older?"
            
            # Ask about immunocompromised
            if "immunocompromised" not in self.asked_questions:
                self.current_question_key = "immunocompromised"
                return "Do you have any immune system conditions? (HIV, cancer treatment, organ transplant, etc.)"
            
            # Move to summary
            self.stage = ConversationStage.SUMMARY
            return self.get_next_question()
        
        elif self.stage == ConversationStage.SUMMARY:
            # Generate summary for confirmation
            summary = self._build_intake_summary()
            return f"Let me confirm what I've gathered:\n\n{summary}\n\nDoes this sound correct?"
        
        elif self.stage == ConversationStage.ASSESSMENT:
            return "Analyzing your symptoms..."
        
        return "Thank you for providing that information."
    
    def process_user_response(self, user_message: str) -> None:
        """Process user's response and update intake based on current question."""
        
        if self.stage == ConversationStage.INITIAL:
            self.intake.chief_complaint = user_message
            self.stage = ConversationStage.CHIEF_COMPLAINT
            self.asked_questions.append("chief_complaint")
        
        elif self.stage == ConversationStage.CHIEF_COMPLAINT:
            key = self.current_question_key
            
            if key == "duration":
                self.intake.duration = user_message
                self.asked_questions.append(key)
            
            elif key == "severity":
                try:
                    severity = int(''.join(c for c in user_message if c.isdigit()))
                    self.intake.severity_scale = min(10, max(0, severity))
                except:
                    pass
                self.asked_questions.append(key)
            
            elif key == "onset":
                self.intake.onset = user_message
                self.asked_questions.append(key)
            
            elif key == "fever":
                self.intake.fever = user_message.lower() in {"yes", "y", "true"}
                self.asked_questions.append(key)
            
            elif key == "pain":
                try:
                    pain = int(''.join(c for c in user_message if c.isdigit()))
                    self.intake.pain_scale = min(10, max(0, pain))
                except:
                    pass
                self.asked_questions.append(key)
            
            elif key == "triggers":
                if user_message.lower() not in {"none", "no", "n/a"}:
                    self.intake.triggers = [t.strip() for t in user_message.split(",")]
                self.asked_questions.append(key)
            
            elif key == "history":
                if user_message.lower() not in {"none", "no", "n/a"}:
                    self.intake.relevant_history = [h.strip() for h in user_message.split(",")]
                self.asked_questions.append(key)
            
            elif key == "meds":
                if user_message.lower() not in {"none", "no", "n/a"}:
                    self.intake.meds = [m.strip() for m in user_message.split(",")]
                self.asked_questions.append(key)
            
            elif key == "allergies":
                if user_message.lower() not in {"none", "no", "n/a"}:
                    self.intake.allergies = [a.strip() for a in user_message.split(",")]
                self.asked_questions.append(key)
        
        elif self.stage == ConversationStage.RED_FLAG_CHECK:
            key = self.current_question_key
            is_yes = user_message.lower() in {"yes", "y", "true"}
            self.intake.red_flag_answers[key] = is_yes
            self.asked_questions.append(key)
        
        elif self.stage == ConversationStage.DEMOGRAPHICS:
            key = self.current_question_key
            
            if key == "age":
                try:
                    age = int(''.join(c for c in user_message if c.isdigit()))
                    self.intake.demographics.age = age
                except:
                    pass
                self.asked_questions.append(key)
            
            elif key == "pregnancy":
                is_yes = user_message.lower() in {"yes", "y", "true"}
                self.intake.demographics.is_pregnant = is_yes
                self.asked_questions.append(key)
            
            elif key == "elderly":
                is_yes = user_message.lower() in {"yes", "y", "true"}
                self.intake.demographics.is_elderly = is_yes
                self.asked_questions.append(key)
            
            elif key == "immunocompromised":
                is_yes = user_message.lower() in {"yes", "y", "true"}
                self.intake.demographics.is_immunocompromised = is_yes
                self.asked_questions.append(key)
        
        elif self.stage == ConversationStage.SUMMARY:
            if user_message.lower() in {"yes", "y", "correct", "correct."}:
                self.stage = ConversationStage.ASSESSMENT
            else:
                # Reset to ask again
                logger.info("User indicated summary was incorrect; resetting.")
                self.stage = ConversationStage.CHIEF_COMPLAINT
                self.asked_questions = ["chief_complaint"]
    
    def _is_pain_related(self) -> bool:
        """Check if chief complaint is pain-related."""
        complaint = (self.intake.chief_complaint or "").lower()
        pain_keywords = ["pain", "ache", "hurt", "sore", "cramp", "tender"]
        return any(kw in complaint for kw in pain_keywords)
    
    def _build_intake_summary(self) -> str:
        """Build a summary of the collected intake information."""
        lines = []
        
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
        
        if self.intake.pain_scale is not None:
            lines.append(f"**Pain:** {self.intake.pain_scale}/10")
        
        if self.intake.triggers:
            lines.append(f"**Triggers:** {', '.join(self.intake.triggers)}")
        
        if self.intake.relevant_history:
            lines.append(f"**Medical History:** {', '.join(self.intake.relevant_history)}")
        
        if self.intake.meds:
            lines.append(f"**Medications:** {', '.join(self.intake.meds)}")
        
        if self.intake.allergies:
            lines.append(f"**Allergies:** {', '.join(self.intake.allergies)}")
        
        # Demographics
        demo_lines = []
        if self.intake.demographics.age:
            demo_lines.append(f"Age: {self.intake.demographics.age}")
        if self.intake.demographics.is_pregnant:
            demo_lines.append("Pregnant: Yes")
        if self.intake.demographics.is_elderly:
            demo_lines.append("Age ≥65: Yes")
        if self.intake.demographics.is_immunocompromised:
            demo_lines.append("Immunocompromised: Yes")
        
        if demo_lines:
            lines.append(f"**Demographics:** {', '.join(demo_lines)}")
        
        # Red flags
        red_flags_triggered = [k for k, v in self.intake.red_flag_answers.items() if v]
        if red_flags_triggered:
            lines.append(f"**Red Flags:** {', '.join(red_flags_triggered)}")
        
        return "\n".join(lines)
    
    def is_ready_for_assessment(self) -> bool:
        """Check if enough information has been gathered for assessment."""
        return self.stage == ConversationStage.ASSESSMENT

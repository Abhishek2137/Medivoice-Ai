"""Conversation management for appointment booking assistant."""

from typing import Dict, Any, Optional
from datetime import datetime

from .extractor import extract_appointment
from .prompts import CONVERSATION_SYSTEM_PROMPT

REQUIRED_FIELDS = [
    "patient_name",
    "specialization",
    "date",
    "time",
]

FIELD_QUESTIONS = {
    "patient_name": "May I know your name?",
    "specialization": "Which type of doctor would you like to see? (e.g., Dermatology, Cardiology, Orthopedics)",
    "date": "Which date would you prefer for the appointment?",
    "time": "What time would you prefer?",
}


class ConversationManager:
    """
    Manages conversation state and flow for appointment booking.
    
    Keeps track of collected information and decides which question to ask next.
    """
    
    def __init__(self):
        """Initialize conversation with empty state."""
        self.state: Dict[str, Any] = {
            "patient_name": None,
            "doctor_name": None,
            "specialization": None,
            "date": None,
            "time": None,
            "symptoms": [],
            "duration": None,
        }
    
    def merge_data(self, new_data: Dict[str, Any]) -> None:
        """
        Merge newly extracted data into conversation state.
        
        Only updates fields that have non-empty values.
        """
        for key, value in new_data.items():
            # Only update if value is meaningful (not None, not empty list/string)
            if value is not None and value != [] and value != "":
                self.state[key] = value
    
    def get_missing_field(self) -> Optional[str]:
        """
        Find the first missing required field.
        
        Returns:
            Field name to ask about, or None if all required fields are present.
        """
        for field in REQUIRED_FIELDS:
            if not self.state.get(field):
                return field
        return None
    
    def question_for_field(self, field: str) -> str:
        """Get conversational question for a missing field."""
        return FIELD_QUESTIONS.get(field, f"Could you provide: {field}?")
    
    def reset(self) -> None:
        """Reset conversation state for a new user or appointment."""
        self.state = {
            "patient_name": None,
            "doctor_name": None,
            "specialization": None,
            "date": None,
            "time": None,
            "symptoms": [],
            "duration": None,
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get current conversation state."""
        return self.state.copy()
    
    def is_complete(self) -> bool:
        """Check if all required fields are collected."""
        return self.get_missing_field() is None
    
    def process(self, user_text: str) -> Dict[str, Any]:
        """
        Process user message and return next action.
        
        Args:
            user_text: The user's message
        
        Returns:
            Dictionary with:
            - status: "collecting_information" or "ready_for_availability"
            - message: Response to show user
            - state: Current conversation state
            - missing_field: Which field we're asking about (if collecting)
        """
        # Extract appointment information from user text
        extracted = extract_appointment(user_text, self.state)
        
        # Merge into existing state
        self.merge_data(extracted)
        
        # Find missing field
        missing = self.get_missing_field()
        
        if missing:
            # Still need more information
            return {
                "status": "collecting_information",
                "message": self.question_for_field(missing),
                "state": self.state.copy(),
                "missing_field": missing,
            }
        
        # All required information collected
        return {
            "status": "ready_for_availability",
            "message": "I have all the information needed. Let me check available doctors and appointment slots for you.",
            "state": self.state.copy(),
            "missing_field": None,
        }
    
    def format_state_for_display(self) -> str:
        """Format current state as a human-readable string."""
        lines = []
        if self.state["patient_name"]:
            lines.append(f"👤 Name: {self.state['patient_name']}")
        if self.state["specialization"]:
            lines.append(f"👨‍⚕️ Doctor Type: {self.state['specialization']}")
        if self.state["date"]:
            lines.append(f"📅 Date: {self.state['date']}")
        if self.state["time"]:
            lines.append(f"⏰ Time: {self.state['time']}")
        if self.state["symptoms"]:
            symptoms_str = ", ".join(self.state["symptoms"])
            lines.append(f"🏥 Symptoms: {symptoms_str}")
        
        return "\n".join(lines) if lines else "No appointment details yet."


# Global conversation manager instance
_global_conversation = ConversationManager()


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    return _global_conversation


def reset_conversation() -> None:
    """Reset the global conversation for a new user."""
    _global_conversation.reset()

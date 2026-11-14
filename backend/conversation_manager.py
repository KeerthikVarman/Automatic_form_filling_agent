"""
Universal Conversation State & Workflow Manager
Maintains multi-turn conversation memory, dynamic question queue, collected user answers,
and supports state preservation across page navigations.
"""

import time
from typing import Dict, List, Optional, Any
from backend.models import (
    WebsiteClassification,
    QuestionStep,
    CollectedField,
    UniversalChatResponse
)
from backend.answer_validator import AnswerValidator

class ConversationSession:
    """Represents a live user session on a website or sequence of pages."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_url: str = ""
        self.page_title: str = ""
        self.classification: Optional[WebsiteClassification] = None
        self.user_intent: str = "understand_page"
        self.workflow_stage: str = "understanding"
        
        # State & Memory
        self.collected_answers: Dict[str, CollectedField] = {}
        self.question_queue: List[QuestionStep] = []
        self.current_question_index: int = 0
        self.conversation_history: List[Dict[str, Any]] = []
        self.created_at: float = time.time()
        self.last_updated: float = time.time()

    def update_page_context(self, url: str, title: str, classification: WebsiteClassification) -> bool:
        """
        Updates the active page context.
        Preserves existing collected answers when navigating between pages on the same domain or workflow.
        Returns True if URL actually changed.
        """
        url_changed = (self.current_url != url)
        self.current_url = url
        self.page_title = title
        self.classification = classification
        self.last_updated = time.time()
        return url_changed

    def add_message(self, sender: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        self.conversation_history.append({
            "sender": sender,
            "role": "user" if sender == "user" else "assistant",
            "text": text,
            "timestamp": time.time(),
            "metadata": metadata or {}
        })
        self.last_updated = time.time()

    def record_answer(self, field_id: str, label: str, raw_val: str, field_type: str = "text") -> CollectedField:
        masked_val = AnswerValidator.mask_sensitive_value(raw_val, field_type=field_type, field_name=label)
        field = CollectedField(
            field_id=field_id,
            label=label,
            raw_value=raw_val,
            masked_value=masked_val,
            verified=True,
            updated_at=time.time()
        )
        self.collected_answers[field_id] = field
        self.last_updated = time.time()
        return field

    def get_current_question(self) -> Optional[QuestionStep]:
        # Filter out already answered questions
        while self.current_question_index < len(self.question_queue):
            q = self.question_queue[self.current_question_index]
            if q.question_id not in self.collected_answers:
                return q
            self.current_question_index += 1
        return None

    def advance_to_next_question(self) -> Optional[QuestionStep]:
        self.current_question_index += 1
        return self.get_current_question()

    def get_collected_summary(self) -> Dict[str, str]:
        """Returns clean dictionary of label -> masked value."""
        return {
            field.label: field.masked_value
            for field in self.collected_answers.values()
        }

    def clear(self):
        self.collected_answers = {}
        self.question_queue = []
        self.current_question_index = 0
        self.conversation_history = []
        self.workflow_stage = "understanding"
        self.last_updated = time.time()

class ConversationManager:
    """Manages active sessions across different tabs and windows."""

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(self, session_id: str = "default_session") -> ConversationSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(session_id)
        return self._sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].clear()

# Global singleton
conversation_manager = ConversationManager()

"""
Universal User Intent Detector
Identifies the user's explicit or implicit objective without making hardcoded assumptions.
"""

import re
from typing import Tuple, List
from backend.models import WebsiteClassification

class IntentDetector:
    """Classifies user queries into operational intents to route the conversational workflow."""

    INTENT_CHIPS_MAP = {
        "government_portal": [
            "What are the requirements?",
            "Who is eligible to apply?",
            "What documents are needed?",
            "Guide me to fill this form",
            "What is this portal for?"
        ],
        "job_portal": [
            "What are the job qualifications?",
            "Help me apply for this role",
            "What documents / resume needed?",
            "What is the hiring process?",
            "Summarize the job description"
        ],
        "university_admissions": [
            "What are the admission requirements?",
            "When is the application deadline?",
            "What documents are required?",
            "Help me apply online",
            "What degrees/courses are offered?"
        ],
        "ecommerce": [
            "Summarize this product",
            "What are the specifications?",
            "Are there return / warranty policies?",
            "Compare options or prices",
            "Help me check out"
        ],
        "banking_finance": [
            "What are the eligibility criteria?",
            "What interest rates / fees apply?",
            "What documents are required?",
            "How do I apply for this account/loan?",
            "Is this portal secure?"
        ],
        "service_booking": [
            "Check availability & dates",
            "What are the booking steps?",
            "What is the cancellation policy?",
            "Help me complete booking",
            "What are the pricing details?"
        ],
        "documentation_info": [
            "Summarize this article",
            "How do I get started?",
            "Explain step-by-step instructions",
            "What are the key takeaways?",
            "Find answers to a question"
        ],
        "general_saas": [
            "What does this software do?",
            "How do I sign up or log in?",
            "Explain pricing plans",
            "Guide me through this page",
            "Contact support"
        ]
    }

    @classmethod
    def detect_intent(cls, user_text: str, classification: WebsiteClassification) -> Tuple[str, str, List[str]]:
        """
        Determines user intent from input text and page context.
        Returns: (intent_key, explanation, suggested_followup_chips)
        """
        text = (user_text or "").strip().lower()
        chips = cls.INTENT_CHIPS_MAP.get(classification.category, cls.INTENT_CHIPS_MAP["general_saas"])

        if not text:
            return "understand_page", "User just opened the page.", chips

        # Greeting or broad inquiry
        if text in ["hi", "hello", "hey", "help", "start", "what can you do", "who are you"]:
            return "greeting_clarification", "User greeted the assistant.", chips

        # Document inquiries
        if any(w in text for w in ["document", "documents", "id proof", "certificate", "attach", "upload", "files needed", "papers"]):
            return "find_documents", "User is inquiring about required documents.", [
                "Who is eligible?",
                "What form fields are required?",
                "Guide me step-by-step"
            ]

        # Eligibility inquiries
        if any(w in text for w in ["eligible", "eligibility", "qualify", "qualification", "who can", "age limit", "criteria", "prerequisite"]):
            return "check_eligibility", "User wants to verify eligibility criteria.", [
                "What documents do I need?",
                "How do I apply step-by-step?",
                "Help me fill the application"
            ]

        # Application / Form Filling guidance
        if any(w in text for w in ["apply", "fill", "register", "submit application", "guide me", "start application", "help me fill", "complete registration", "form"]):
            return "fill_application", "User wants guided interactive assistance to apply or fill out the page.", [
                "What documents should I prepare?",
                "What is the next question?",
                "Review collected details"
            ]

        # Account creation / Registration
        if any(w in text for w in ["sign up", "signup", "create account", "new user", "register account", "join"]):
            return "register_account", "User wants to create a new user account.", [
                "What information is needed to register?",
                "Guide me through registration"
            ]

        # Website understanding / Overview
        if any(w in text for w in ["what is this", "explain this page", "summary", "summarize", "overview", "what does this site do", "purpose"]):
            return "understand_page", "User wants an overview of the current webpage.", chips

        # Troubleshooting / Error
        if any(w in text for w in ["error", "issue", "problem", "failed", "stuck", "invalid", "cannot", "why"]):
            return "troubleshoot_issue", "User encountered an issue on the page.", [
                "How do I fix this?",
                "What are the correct requirements?",
                "Contact official support"
            ]

        # Default: Specific content query
        return "search_information", "User asked a specific content question based on page text.", chips

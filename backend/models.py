from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class FieldRequirement(BaseModel):
    field_id: str = Field(description="Unique identifier for the field, e.g. aadhaar_number or entrepreneur_name")
    label: str = Field(description="Human readable label or prompt seen on website")
    element_ref: Optional[str] = Field(default=None, description="The snapshot ref e.g. e53")
    field_type: str = Field(default="text", description="text, number, select, checkbox, radio")
    is_mandatory: bool = Field(default=True, description="Whether this field is mandatory to proceed")
    format_expectation: str = Field(default="", description="Description of format, e.g. 12 digit number")
    validation_regex: Optional[str] = Field(default=None, description="Regex pattern for client/server validation")
    validation_message: Optional[str] = Field(default=None, description="Guidance message if input fails validation")
    options: Optional[List[str]] = Field(default=None, description="Available dropdown options if select")

class ActionButton(BaseModel):
    label: str
    element_ref: Optional[str] = None
    action_type: str = "submit"

class PageAnalysis(BaseModel):
    page_title: str = ""
    current_url: str = ""
    step_name: str = "initial"
    instructions: List[str] = []
    fields: List[FieldRequirement] = []
    consent_checkbox_ref: Optional[str] = None
    action_buttons: List[ActionButton] = []
    has_otp: bool = False
    otp_details: Optional[str] = None
    has_captcha: bool = False
    is_authenticated: bool = False
    raw_summary: str = ""

class ChatMessage(BaseModel):
    id: str
    sender: str  # "bot", "user", "system"
    text: str
    timestamp: float
    message_type: str = "text"  # "text", "question", "otp_alert", "captcha_alert", "success_alert", "link_card", "error"
    field_id: Optional[str] = None
    options: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class BrowserStatus(BaseModel):
    is_connected: bool = False
    current_url: str = ""
    automation_status: str = "idle"  # "idle", "navigating", "inspecting", "awaiting_user_input", "filling_form", "awaiting_otp", "awaiting_captcha", "verified", "error"
    last_inspection_summary: str = "Not inspected yet"
    detected_step: str = "none"
    last_updated: float = 0.0

class WebsiteContextPayload(BaseModel):
    url: str
    title: str = ""
    headings: List[str] = []
    page_text: str = ""
    form_elements: Optional[List[Dict[str, Any]]] = None
    question: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None

class RequirementsBreakdown(BaseModel):
    eligibility: List[str] = []
    required_documents: List[str] = []
    key_form_fields: List[str] = []
    procedure_steps: List[str] = []

class WebsiteAnalysisResponse(BaseModel):
    summary: str = ""
    portal_purpose: str = ""
    requirements: RequirementsBreakdown = Field(default_factory=RequirementsBreakdown)
    answer: str = ""
    unsupported_info: List[str] = []

# ==========================================
# UNIVERSAL WEBSITE ASSISTANT MODELS
# ==========================================

class FormElementInfo(BaseModel):
    tag: str = "input"
    type: str = "text"
    name: str = ""
    id: str = ""
    label: str = ""
    placeholder: str = ""
    required: bool = False
    options: Optional[List[str]] = None
    value: Optional[str] = None

class UniversalPagePayload(BaseModel):
    session_id: str = "default_session"
    url: str
    title: str = ""
    meta_description: Optional[str] = None
    headings: List[str] = []
    page_text: str = ""
    form_elements: List[FormElementInfo] = []
    navigation_links: List[Dict[str, str]] = []
    user_message: Optional[str] = None
    force_refresh: bool = False
    conversation_history: Optional[List[Dict[str, Any]]] = None

class WebsiteClassification(BaseModel):
    category: str = "general"
    # Options: government_portal, job_portal, university_admissions, ecommerce, banking_finance, service_booking, documentation_info, social_community, general_saas, login_registration
    page_type: str = "general_page"
    # Options: login, registration, application_form, product_catalog, article_info, dashboard, search_results, checkout, contact_support
    site_name: str = ""
    page_purpose: str = ""
    confidence: float = 0.9

class QuestionStep(BaseModel):
    question_id: str
    field_name: str
    question_text: str
    field_type: str = "text"  # text, email, phone, number, select, date, boolean, file
    explanation: str = ""  # Why this information is required
    is_mandatory: bool = True
    options: Optional[List[str]] = None
    validation_hint: Optional[str] = None

class CollectedField(BaseModel):
    field_id: str
    label: str
    raw_value: str
    masked_value: str
    verified: bool = True
    updated_at: float = 0.0

class UniversalChatResponse(BaseModel):
    session_id: str
    classification: WebsiteClassification = Field(default_factory=WebsiteClassification)
    user_intent: str = "understand_page"
    assistant_message: str = ""
    current_question: Optional[QuestionStep] = None
    progress_text: Optional[str] = None
    collected_summary: Dict[str, str] = Field(default_factory=dict)
    suggested_chips: List[str] = Field(default_factory=list)
    workflow_stage: str = "understanding"  # understanding, intent_clarification, question_flow, completed, information_answering
    unsupported_notes: List[str] = Field(default_factory=list)

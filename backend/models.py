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



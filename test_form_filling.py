"""
Pytest Suite: Universal Form Filling & Browser Automation
Verifies dynamic field mapping, snapshot ref resolution, and answer validation across ANY website.
"""

import asyncio
from backend.groq_service import GroqService
from backend.validator import AnswerValidator

def test_universal_groq_field_mapping():
    """Test that Groq dynamically maps arbitrary user data to live accessibility snapshot elements."""
    service = GroqService()
    
    mock_snapshot = """
- generic [ref=e10]:
  - form "Customer Registration" [ref=e11]:
    - text: Full Name
    - textbox "Enter your full name" [ref=e12]
    - text: Email Address
    - textbox "name@example.com" [ref=e13]
    - text: Contact Number
    - textbox "Phone Number" [ref=e14]
    - text: Preferred Delivery Time
    - combobox "Delivery Time" [ref=e15]:
      - option "Morning"
      - option "Afternoon"
    - checkbox "I accept the terms and conditions" [ref=e16]
    - button "Submit Application" [ref=e17]
    """

    user_data = {
        "full_name": "Jane Doe",
        "email_address": "jane.doe@example.com",
        "contact_number": "+1-555-0199"
    }

    result = service.map_data_to_form_fields(
        snapshot_text=mock_snapshot,
        collected_answers=user_data,
        current_url="https://example.com/register"
    )

    mappings = result.get("mappings", [])
    assert len(mappings) >= 2, f"Expected at least 2 mappings, got {len(mappings)}"
    
    mapped_keys = {m["field_key"]: m["element_ref"] for m in mappings}
    assert "full_name" in mapped_keys
    assert mapped_keys["full_name"] == "e12"
    assert "email_address" in mapped_keys
    assert mapped_keys["email_address"] == "e13"

def test_universal_answer_validation():
    """Test that generic fields (emails, phone, names, text) are validated accurately."""
    # Email
    valid, val, msg = AnswerValidator.validate_answer("test@domain.com", "email")
    assert valid, f"Expected valid email: {msg}"
    
    invalid, _, msg = AnswerValidator.validate_answer("invalid-email", "email")
    assert not invalid

    # Phone
    valid, val, msg = AnswerValidator.validate_answer("+1 (555) 234-5678", "phone")
    assert valid

    # Generic Name
    valid, val, msg = AnswerValidator.validate_answer("Dr. Evelyn Reed", "name")
    assert valid

"""
Universal Field Validator
Provides validation for arbitrary website fields using AnswerValidator.
"""

import re
from typing import Tuple, Optional, List
from backend.answer_validator import AnswerValidator

def validate_name(value: str) -> Tuple[bool, str, str]:
    """Validate a person's or applicant's name."""
    is_valid, cleaned, msg = AnswerValidator.validate_answer(
        user_input=value,
        field_name="Full Name",
        field_type="text",
        is_mandatory=True
    )
    return is_valid, cleaned, msg

def validate_generic_field(
    value: str,
    is_mandatory: bool,
    regex: Optional[str] = None,
    validation_msg: Optional[str] = None,
    field_type: str = "text",
    options: Optional[List[str]] = None,
    field_name: str = "Field"
) -> Tuple[bool, str, str]:
    """Universal validator for any arbitrary form field."""
    cleaned = value.strip()
    if is_mandatory and not cleaned:
        return False, "", validation_msg or f"{field_name} is mandatory. Please provide a value."

    if cleaned and regex:
        try:
            if not re.match(regex, cleaned):
                return False, cleaned, validation_msg or f"Invalid format for {field_name}."
        except re.error:
            pass

    return AnswerValidator.validate_answer(
        user_input=value,
        field_name=field_name,
        field_type=field_type,
        options=options,
        is_mandatory=is_mandatory
    )

def validate_aadhaar(value: str) -> Tuple[bool, str, str]:
    """Backward compatibility alias if a field specifically requests an ID number."""
    return AnswerValidator.validate_answer(value, field_name="ID Number", field_type="text")

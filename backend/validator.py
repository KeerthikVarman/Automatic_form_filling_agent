import re
from typing import Tuple, Optional

# Verhoeff algorithm tables for Aadhaar checksum validation
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

def validate_verhoeff(number_str: str) -> bool:
    """Validate a numeric string using the Verhoeff algorithm."""
    c = 0
    reversed_digits = [int(d) for d in reversed(number_str)]
    for i, digit in enumerate(reversed_digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][digit]]
    return c == 0

def validate_aadhaar(value: str) -> Tuple[bool, str, str]:
    """
    Validate an Aadhaar number.
    Returns (is_valid, cleaned_value, error_message)
    """
    cleaned = re.sub(r"[\s\-]", "", value.strip())
    
    if not cleaned:
        return False, "", "Aadhaar number is mandatory. Please enter your 12-digit Aadhaar number."
    
    if not cleaned.isdigit():
        return False, cleaned, "Aadhaar number must contain only numeric digits (0-9)."
    
    if len(cleaned) != 12:
        return False, cleaned, f"Aadhaar number must be exactly 12 digits. You entered {len(cleaned)} digits."
    
    if cleaned[0] in ("0", "1"):
        return False, cleaned, "Valid Aadhaar numbers do not start with 0 or 1. Please check your card."
        
    # Check Verhoeff checksum
    if not validate_verhoeff(cleaned):
        return False, cleaned, "Aadhaar number failed checksum validation. Please verify the 12 digits carefully."
        
    return True, cleaned, ""

def validate_name(value: str) -> Tuple[bool, str, str]:
    """
    Validate Entrepreneur Name as per Aadhaar.
    Returns (is_valid, cleaned_value, error_message)
    """
    cleaned = value.strip()
    if not cleaned:
        return False, "", "Name of Entrepreneur is mandatory as per Aadhaar."
        
    if len(cleaned) < 2:
        return False, cleaned, "Name must be at least 2 characters long."
        
    if len(cleaned) > 100:
        return False, cleaned, "Name cannot exceed 100 characters."
        
    # Check that name contains allowed characters: alphabets, spaces, dots, hyphens
    if not re.match(r"^[A-Za-z\s\.\-\']+$", cleaned):
        return False, cleaned, "Name can only contain alphabets, spaces, dots and hyphens as per Aadhaar records."
        
    return True, cleaned, ""

def validate_generic_field(value: str, is_mandatory: bool, regex: Optional[str] = None, validation_msg: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Generic field validator based on requirements identified by Groq.
    """
    cleaned = value.strip()
    if is_mandatory and not cleaned:
        return False, "", validation_msg or "This field is mandatory. Please enter a value."
        
    if cleaned and regex:
        try:
            if not re.match(regex, cleaned):
                return False, cleaned, validation_msg or f"Invalid format. Please match the requested format: {regex}"
        except re.error:
            pass  # Ignore invalid regex from LLM
            
    return True, cleaned, ""


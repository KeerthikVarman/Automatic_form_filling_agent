"""
Universal Answer Validator & Sensitive Data Sanitizer
Validates user input dynamically across multiple field types, supports user corrections,
and masks sensitive information before logging or storing.
"""

import re
from typing import Tuple, Optional, List, Dict, Any

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

def validate_verhoeff(number_str: str) -> bool:
    c = 0
    reversed_digits = [int(d) for d in reversed(number_str)]
    for i, digit in enumerate(reversed_digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][digit]]
    return c == 0

class AnswerValidator:
    """Universal validator for dynamic form fields and conversational inputs."""

    @staticmethod
    def mask_sensitive_value(value: str, field_type: str = "text", field_name: str = "") -> str:
        """
        Masks sensitive data for user display and logs.
        Never reveals passwords, full Aadhaar, or sensitive account numbers.
        """
        if not value:
            return ""
        
        name_lower = (field_name or "").lower()
        type_lower = (field_type or "").lower()

        # Passwords / OTPs
        if any(w in name_lower for w in ["password", "otp", "pin", "cvv", "secret"]) or type_lower == "password":
            return "••••••••"

        # Aadhaar (12 digits)
        clean_num = re.sub(r"[\s\-]", "", value)
        if "aadhaar" in name_lower or (clean_num.isdigit() and len(clean_num) == 12):
            return f"XXXX-XXXX-{clean_num[-4:]}"

        # Credit card or Account number (12-16 digits)
        if clean_num.isdigit() and len(clean_num) in (15, 16):
            return f"••••-••••-••••-{clean_num[-4:]}"

        # Email
        if "@" in value and type_lower in ["email", "text"]:
            parts = value.split("@", 1)
            local = parts[0]
            domain = parts[1]
            if len(local) <= 2:
                masked_local = local[0] + "*"
            else:
                masked_local = local[0] + ("*" * (len(local) - 2)) + local[-1]
            return f"{masked_local}@{domain}"

        # Phone
        if type_lower in ["phone", "tel"] or "phone" in name_lower or "mobile" in name_lower:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 10:
                return f"******{digits[-4:]}"

        return value

    @staticmethod
    def detect_correction(user_text: str, collected_fields: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Detects if the user is trying to correct a previously provided answer.
        E.g.: "Actually my email is john@doe.com" or "Wait, change name to Alice"
        Returns: (is_correction, matched_field_id, new_value)
        """
        text = user_text.strip()
        correction_patterns = [
            r"^(?:actually|wait|correction|change|update|no wait|scratch that)[,\s]+(?:my\s+)?([a-zA-Z_\s]+?)\s+(?:is|to|should be)\s+(.+)$",
            r"^change\s+(?:my\s+)?([a-zA-Z_\s]+?)\s+to\s+(.+)$",
            r"^my\s+([a-zA-Z_\s]+?)\s+is\s+actually\s+(.+)$"
        ]

        for pat in correction_patterns:
            m = re.match(pat, text, re.IGNORECASE)
            if m:
                target_name = m.group(1).strip().lower().replace(" ", "_")
                new_val = m.group(2).strip()
                # Find matching field in collected_fields
                for fid in collected_fields.keys():
                    if target_name in fid.lower() or fid.lower() in target_name:
                        return True, fid, new_val
                # If name mentioned directly matches
                return True, target_name, new_val

        return False, None, None

    @classmethod
    def validate_answer(
        cls,
        user_input: str,
        field_name: str,
        field_type: str = "text",
        options: Optional[List[str]] = None,
        is_mandatory: bool = True
    ) -> Tuple[bool, str, str]:
        """
        Validates user input against expected field requirements.
        Returns: (is_valid, cleaned_value, error_or_guidance_message)
        """
        val = user_input.strip()

        if not val:
            if is_mandatory:
                return False, "", f"{field_name} is required. Please provide a valid value."
            return True, "", ""

        ftype = (field_type or "text").lower()
        fname = (field_name or "").lower()

        # Email Validation
        if ftype == "email" or "email" in fname:
            email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
            if not re.match(email_pattern, val):
                return False, val, "Please enter a valid email address (e.g. name@example.com)."
            return True, val.lower(), "Email format valid."

        # Phone / Mobile Validation
        if ftype in ["phone", "tel"] or "mobile" in fname or "phone" in fname:
            cleaned_digits = re.sub(r"[\s\-\+\(\)]", "", val)
            if not cleaned_digits.isdigit():
                return False, val, "Phone number must contain numeric digits."
            if len(cleaned_digits) < 7 or len(cleaned_digits) > 15:
                return False, val, f"Please enter a valid phone number with 7 to 15 digits (entered {len(cleaned_digits)})."
            return True, cleaned_digits, "Phone number valid."

        # Aadhaar Validation (if specified)
        if "aadhaar" in fname:
            cleaned_aadhaar = re.sub(r"[\s\-]", "", val)
            if not cleaned_aadhaar.isdigit():
                return False, val, "Aadhaar number must contain only numeric digits."
            if len(cleaned_aadhaar) != 12:
                return False, val, f"Aadhaar number must be exactly 12 digits (entered {len(cleaned_aadhaar)})."
            if cleaned_aadhaar[0] in ("0", "1"):
                return False, val, "Valid Aadhaar numbers do not start with 0 or 1."
            if not validate_verhoeff(cleaned_aadhaar):
                return False, val, "Aadhaar number failed checksum verification. Please re-check the 12 digits."
            return True, cleaned_aadhaar, "Aadhaar number verified."

        # PAN Validation (if specified)
        if "pan" in fname and "company" not in fname:
            cleaned_pan = val.upper().replace(" ", "")
            if len(cleaned_pan) == 10 and re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", cleaned_pan):
                return True, cleaned_pan, "PAN format valid."
            # If user entered something else for generic site, don't hard reject unless clearly PAN
            if "pan" == fname or "pan card" in fname:
                return False, val, "PAN must follow standard format (5 letters, 4 numbers, 1 letter, e.g. ABCDE1234F)."

        # Number / Integer / Float Validation
        if ftype == "number" or "quantity" in fname or "age" in fname or "year" in fname or "amount" in fname:
            cleaned_num = re.sub(r"[,\$€₹]", "", val)
            try:
                if "." in cleaned_num:
                    num_val = float(cleaned_num)
                else:
                    num_val = int(cleaned_num)
                return True, str(num_val), "Number validated."
            except ValueError:
                return False, val, f"Please enter a valid numeric value for {field_name}."

        # Date Validation
        if ftype == "date" or "date" in fname or "dob" in fname:
            # Match common patterns YYYY-MM-DD or DD/MM/YYYY or DD-MM-YYYY
            date_match = re.match(r"^(\d{1,4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,4})$", val)
            if date_match:
                return True, val, "Date recorded."
            # Also allow text dates e.g. "15 August 1995"
            if len(val) >= 4 and any(m in val.lower() for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                return True, val, "Date recorded."
            return False, val, "Please enter a valid date (e.g. DD/MM/YYYY or YYYY-MM-DD)."

        # Select / Dropdown Validation
        if options and len(options) > 0:
            val_lower = val.lower()
            # Exact or partial match in options
            for opt in options:
                if opt.lower() == val_lower or val_lower in opt.lower():
                    return True, opt, f"Selected option: {opt}"
            return False, val, f"Please choose from the available options: {', '.join(options[:5])}."

        # Boolean / Yes-No
        if ftype == "boolean" or "agree" in fname or "confirm" in fname:
            val_lower = val.lower()
            if val_lower in ["yes", "y", "true", "agree", "ok", "sure", "confirmed"]:
                return True, "Yes", "Confirmed."
            if val_lower in ["no", "n", "false", "disagree", "cancel"]:
                return True, "No", "Declined."
            return False, val, "Please answer with 'Yes' or 'No'."

        # General Name Validation
        if "name" in fname and not any(k in fname for k in ["username", "file", "company", "domain"]):
            if len(val) < 2:
                return False, val, "Name must be at least 2 characters long."
            if re.search(r"[0-9!@#\$%\^&\*_\+=\[\]\{\}\|;:<>\?~]", val):
                return False, val, "Name should not contain numbers or special characters."
            return True, val.strip(), "Name recorded."

        # Default text check
        if len(val) > 1000:
            return False, val[:100] + "...", "Input text exceeds maximum length of 1000 characters."

        return True, val, "Input accepted."

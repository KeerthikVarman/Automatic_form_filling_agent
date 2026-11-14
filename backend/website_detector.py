"""
Universal Website & Page Type Detector
Analyzes URL structure, page titles, headings, meta tags, and interactive form structures
to classify any arbitrary website dynamically without hardcoded assumptions.
"""

import re
from urllib.parse import urlparse
from typing import Dict, Any, List
from backend.models import WebsiteClassification, FormElementInfo

class WebsiteDetector:
    """Classifies any website dynamically into domain categories and operational page types."""

    @staticmethod
    def classify_website(
        url: str,
        title: str,
        headings: List[str],
        page_text: str,
        form_elements: List[FormElementInfo],
        meta_description: str = ""
    ) -> WebsiteClassification:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
        title_lower = (title or "").lower()
        headings_lower = " ".join(headings).lower()
        combined_text = (title_lower + " " + headings_lower + " " + (meta_description or "").lower())[:1500]

        # Extract domain name branding
        domain_parts = hostname.split(".")
        if len(domain_parts) >= 2:
            site_name = domain_parts[-2].capitalize() if domain_parts[-2] not in ["gov", "co", "nic", "org", "edu", "ac"] else domain_parts[0].capitalize()
        else:
            site_name = hostname

        has_password_input = any(f.type == "password" for f in form_elements)
        has_submit_btn = any(f.tag == "button" or f.type == "submit" for f in form_elements)
        input_count = len([f for f in form_elements if f.tag in ["input", "select", "textarea"]])

        # ------------------------------------------------------------------
        # Category Detection Heuristics
        # ------------------------------------------------------------------
        category = "general_saas"
        confidence = 0.85

        if any(h in hostname for h in [".gov", ".nic.", "government", "parivahan", "passport", "uidai", "gst", "incometax", "portal.gov"]) or \
           any(w in combined_text for w in ["government of", "ministry of", "citizen portal", "national portal", "official portal", "public service"]):
            category = "government_portal"
            confidence = 0.95

        elif any(h in hostname for h in ["careers", "naukri", "linkedin", "indeed", "monster", "glassdoor", "jobs", "internshala", "lever.co", "greenhouse.io", "workday"]) or \
             any(w in combined_text for w in ["job opening", "apply for this position", "submit resume", "job description", "careers", "we are hiring", "employment opportunity"]):
            category = "job_portal"
            confidence = 0.95

        elif any(h in hostname for h in [".edu", ".ac.", "university", "college", "admissions", "school", "campus"]) or \
             any(w in combined_text for w in ["admissions", "academic program", "undergraduate", "postgraduate", "student portal", "tuition", "enrollment", "course curriculum"]):
            category = "university_admissions"
            confidence = 0.95

        elif any(h in hostname for h in ["amazon", "ebay", "walmart", "flipkart", "shop", "store", "myntra", "etsy", "aliexpress"]) or \
             any(w in combined_text for w in ["add to cart", "buy now", "shopping cart", "free shipping", "product details", "price: ₹", "price: $", "in stock", "out of stock"]):
            category = "ecommerce"
            confidence = 0.95

        elif any(h in hostname for h in ["bank", "chase", "hdfc", "sbi", "icici", "wellsfargo", "citi", "paypal", "stripe", "creditcard", "loan"]) or \
             any(w in combined_text for w in ["internet banking", "personal loan", "interest rate", "account balance", "routing number", "credit score", "fixed deposit"]):
            category = "banking_finance"
            confidence = 0.95

        elif any(h in hostname for h in ["booking", "makemytrip", "airbnb", "expedia", "uber", "irctc", "flight", "hotel"]) or \
             any(w in combined_text for w in ["book now", "check availability", "check-in date", "reservation", "flight status", "seat selection"]):
            category = "service_booking"
            confidence = 0.90

        elif any(h in hostname for h in ["wikipedia", "docs.", "documentation", "blog", "medium", "support.", "help."]) or \
             any(w in combined_text for w in ["documentation", "api reference", "getting started", "table of contents", "knowledge base", "frequently asked questions"]):
            category = "documentation_info"
            confidence = 0.90

        # ------------------------------------------------------------------
        # Page Type Detection Heuristics
        # ------------------------------------------------------------------
        page_type = "information_article"
        page_purpose = f"Viewing information on {site_name}."

        if has_password_input and ("login" in path or "signin" in path or "login" in title_lower or "sign in" in combined_text) and input_count <= 4:
            page_type = "login"
            page_purpose = f"User authentication and sign-in to {site_name}."
        elif has_password_input and any(w in (path + " " + combined_text) for w in ["signup", "sign-up", "register", "create-account", "new user"]):
            page_type = "registration"
            page_purpose = f"Creating a new user account on {site_name}."
        elif input_count >= 2 and any(w in (path + " " + combined_text) for w in ["apply", "registration", "form", "submit", "application", "onboarding", "step", "verification"]):
            page_type = "application_form"
            page_purpose = f"Completing an online application or multi-field submission on {site_name}."
        elif any(w in (path + " " + combined_text) for w in ["checkout", "cart", "payment", "order-summary", "place order"]):
            page_type = "checkout"
            page_purpose = f"Reviewing purchase details and completing payment on {site_name}."
        elif category == "ecommerce" and any(w in combined_text for w in ["add to cart", "buy now", "specifications", "reviews", "features"]):
            page_type = "product_catalog"
            page_purpose = f"Browsing product catalog and purchasing options on {site_name}."
        elif any(w in (path + " " + combined_text) for w in ["search", "results", "query", "filter"]):
            page_type = "search_results"
            page_purpose = f"Browsing search results and directory listings on {site_name}."
        elif any(w in (path + " " + combined_text) for w in ["dashboard", "home", "console", "overview", "analytics", "my-account"]):
            page_type = "dashboard"
            page_purpose = f"Accessing account dashboard or control panel on {site_name}."

        return WebsiteClassification(
            category=category,
            page_type=page_type,
            site_name=site_name,
            page_purpose=page_purpose,
            confidence=confidence
        )

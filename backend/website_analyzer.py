"""
Universal Website Analyzer & Dynamic Workflow Engine
Powered by Groq LLM with multiple model fallbacks.
Analyzes any website dynamically without hardcoding, generates questions one at a time,
and formulates conversational responses grounded strictly in the webpage context.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from groq import Groq

from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODELS
from backend.models import (
    WebsiteClassification,
    QuestionStep,
    FormElementInfo,
    UniversalChatResponse,
    UniversalPagePayload
)
from backend.website_detector import WebsiteDetector
from backend.intent_detector import IntentDetector
from backend.answer_validator import AnswerValidator
from backend.conversation_manager import conversation_manager, ConversationSession

logger = logging.getLogger("udyam_assistant.universal")

class WebsiteAnalyzer:
    """Universal AI analysis engine for web pages and conversational workflows."""

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)

    def _call_groq_json(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, Any]:
        """Calls Groq with fallback models and enforces JSON output."""
        models_to_try = [GROQ_MODEL] + [m for m in GROQ_FALLBACK_MODELS if m != GROQ_MODEL]
        last_error = None

        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature
                )
                raw_json = response.choices[0].message.content
                return json.loads(raw_json)
            except Exception as e:
                logger.warning(f"Groq error with {model}: {e}")
                last_error = e

        logger.error(f"All Groq models failed: {last_error}")
        return {"error": str(last_error)}

    def analyze_page_on_open(self, payload: UniversalPagePayload) -> UniversalChatResponse:
        """
        Invoked when the side panel opens or user navigates to a new page.
        Classifies the site, extracts purpose and requirements, and greets the user with options.
        """
        session = conversation_manager.get_or_create_session(payload.session_id)
        
        # 1. Run heuristic website classification
        classification = WebsiteDetector.classify_website(
            url=payload.url,
            title=payload.title,
            headings=payload.headings,
            page_text=payload.page_text,
            form_elements=payload.form_elements,
            meta_description=payload.meta_description or ""
        )

        url_changed = session.update_page_context(payload.url, payload.title, classification)

        # 2. Extract forms summary for LLM prompt
        forms_summary = self._build_forms_summary(payload.form_elements)
        cleaned_text = (payload.page_text or "")[:12000]

        system_prompt = f"""You are a Universal AI Browser Assistant embedded as a side panel alongside a live webpage.
CRITICAL DIRECTIVES:
1. You work universally on ANY website (government, job portal, university, ecommerce, banking, news, SaaS, etc.).
2. NEVER assume a hardcoded site or portal. Dynamically understand THIS specific page from its URL, title, headings, and text.
3. Understand:
   - What is this website ({classification.site_name}) and its exact purpose?
   - What can a user accomplish on this page?
   - What information, documents, or details are required from the user?
   - What is the step-by-step workflow?
4. Determine a list of dynamic questions that would need to be asked if the user wants to apply, register, or complete this page's goal.
5. Create a friendly, professional greeting introducing the page and asking what the user would like to do.
6. GROUNDING RULE: Ground all facts strictly in the provided webpage text. If something is not on the page, do NOT invent it.
7. Return valid JSON matching the schema below.

JSON SCHEMA:
{{
  "portal_purpose": "Clear 1-2 sentence description of what this page/website is used for",
  "key_capabilities": ["What user can do 1", "What user can do 2"],
  "required_documents": ["Document 1", "Document 2"],
  "greeting_message": "Friendly greeting explaining what this page is and asking what they want to achieve",
  "suggested_questions": [
    {{
      "question_id": "field_unique_id",
      "field_name": "Field Label",
      "question_text": "Polite question asking for this info",
      "field_type": "text|email|phone|number|select|date|boolean",
      "explanation": "Why this specific info is needed for this page",
      "is_mandatory": true,
      "options": []
    }}
  ]
}}"""

        user_content = f"""Current Webpage URL: {payload.url}
Title: {payload.title}
Headings on Page:
{json.dumps(payload.headings[:25], indent=2)}

Detected Forms & Interactive Inputs:
{forms_summary}

Visible Webpage Content:
\"\"\"
{cleaned_text}
\"\"\"
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        llm_data = self._call_groq_json(messages)

        # Populate question queue if application/form page
        suggested_q_raw = llm_data.get("suggested_questions", [])
        question_steps = []
        for q in suggested_q_raw:
            question_steps.append(QuestionStep(
                question_id=q.get("question_id", f"q_{len(question_steps)}"),
                field_name=q.get("field_name", "Field"),
                question_text=q.get("question_text", "Please provide this detail:"),
                field_type=q.get("field_type", "text"),
                explanation=q.get("explanation", ""),
                is_mandatory=q.get("is_mandatory", True),
                options=q.get("options")
            ))

        if question_steps:
            session.question_queue = question_steps

        # Default greeting if LLM failed
        greeting = llm_data.get("greeting_message")
        if not greeting:
            greeting = f"I've analyzed **{classification.site_name}** ({payload.title}). {classification.page_purpose}\n\nWhat would you like to accomplish on this page today?"

        session.add_message("bot", greeting)

        # Generate contextual chips
        _, _, default_chips = IntentDetector.detect_intent("", classification)

        return UniversalChatResponse(
            session_id=session.session_id,
            classification=classification,
            user_intent="understand_page",
            assistant_message=greeting,
            current_question=None,
            progress_text=None,
            collected_summary=session.get_collected_summary(),
            suggested_chips=default_chips,
            workflow_stage="understanding",
            unsupported_notes=[]
        )

    def process_chat_message(self, payload: UniversalPagePayload) -> UniversalChatResponse:
        """
        Main conversational turn:
        1. Checks for user correction ("Wait, my email is...")
        2. If in question flow: validates answer, saves to session memory, advances to next question.
        3. Detects user intent.
        4. Answers questions grounded in page context or initiates 1-by-1 question asking.
        """
        session = conversation_manager.get_or_create_session(payload.session_id)
        user_text = (payload.user_message or "").strip()
        session.add_message("user", user_text)

        classification = session.classification or WebsiteDetector.classify_website(
            url=payload.url,
            title=payload.title,
            headings=payload.headings,
            page_text=payload.page_text,
            form_elements=payload.form_elements
        )

        # ------------------------------------------------------------------
        # Step A: Check for Correction of Previous Answer
        # ------------------------------------------------------------------
        is_corr, corr_fid, corr_val = AnswerValidator.detect_correction(user_text, session.collected_answers)
        if is_corr and corr_fid and corr_val:
            existing_label = session.collected_answers[corr_fid].label if corr_fid in session.collected_answers else corr_fid.replace("_", " ").title()
            field_rec = session.record_answer(corr_fid, existing_label, corr_val)
            ack_msg = f"Got it! I have updated your **{existing_label}** to `{field_rec.masked_value}`."
            
            # Resume current question
            curr_q = session.get_current_question()
            if curr_q:
                ack_msg += f"\n\nContinuing with our next step:\n**{curr_q.question_text}**"
                if curr_q.explanation:
                    ack_msg += f"\n*(Reason: {curr_q.explanation})*"

            session.add_message("bot", ack_msg)
            return UniversalChatResponse(
                session_id=session.session_id,
                classification=classification,
                user_intent=session.user_intent,
                assistant_message=ack_msg,
                current_question=curr_q,
                progress_text=self._format_progress(session),
                collected_summary=session.get_collected_summary(),
                suggested_chips=["Change another answer", "Review all collected info"],
                workflow_stage="question_flow"
            )

        # ------------------------------------------------------------------
        # Step B: Check if User is Answering Current Pending Question
        # ------------------------------------------------------------------
        active_question = session.get_current_question()
        if session.workflow_stage == "question_flow" and active_question:
            # Validate answer against current question requirement
            is_valid, cleaned_val, val_msg = AnswerValidator.validate_answer(
                user_input=user_text,
                field_name=active_question.field_name,
                field_type=active_question.field_type,
                options=active_question.options,
                is_mandatory=active_question.is_mandatory
            )

            if not is_valid:
                # Answer was invalid -> explain why and re-ask the SAME question
                retry_msg = f"⚠️ {val_msg}\n\n**{active_question.question_text}**"
                if active_question.explanation:
                    retry_msg += f"\n*(Note: {active_question.explanation})*"
                session.add_message("bot", retry_msg)

                return UniversalChatResponse(
                    session_id=session.session_id,
                    classification=classification,
                    user_intent=session.user_intent,
                    assistant_message=retry_msg,
                    current_question=active_question,
                    progress_text=self._format_progress(session),
                    collected_summary=session.get_collected_summary(),
                    suggested_chips=active_question.options or ["Explain why this is required", "Skip optional field"],
                    workflow_stage="question_flow"
                )

            # Valid answer -> record in session memory
            session.record_answer(active_question.question_id, active_question.field_name, cleaned_val, active_question.field_type)

            # Advance to next question
            next_q = session.advance_to_next_question()
            if next_q:
                resp_text = f"Thank you! Recorded **{active_question.field_name}**.\n\n**{next_q.question_text}**"
                if next_q.explanation:
                    resp_text += f"\n*(Why needed: {next_q.explanation})*"
                session.add_message("bot", resp_text)

                return UniversalChatResponse(
                    session_id=session.session_id,
                    classification=classification,
                    user_intent="fill_application",
                    assistant_message=resp_text,
                    current_question=next_q,
                    progress_text=self._format_progress(session),
                    collected_summary=session.get_collected_summary(),
                    suggested_chips=next_q.options or ["Change previous answer", "Why is this needed?"],
                    workflow_stage="question_flow"
                )
            else:
                # Completed all questions!
                session.workflow_stage = "completed"
                summary_lines = [f"- **{k}**: `{v}`" for k, v in session.get_collected_summary().items()]
                summary_block = "\n".join(summary_lines) if summary_lines else "All details verified."
                complete_msg = f"🎉 **All required details for this page have been collected!**\n\n### Summary of Your Details:\n{summary_block}\n\nYou are ready to proceed with submission on **{classification.site_name}**."
                session.add_message("bot", complete_msg)

                return UniversalChatResponse(
                    session_id=session.session_id,
                    classification=classification,
                    user_intent="completed",
                    assistant_message=complete_msg,
                    current_question=None,
                    progress_text="100% Completed",
                    collected_summary=session.get_collected_summary(),
                    suggested_chips=["Review details", "Start over", "Ask another question"],
                    workflow_stage="completed"
                )

        # ------------------------------------------------------------------
        # Step C: Detect User Intent
        # ------------------------------------------------------------------
        intent, intent_desc, suggested_chips = IntentDetector.detect_intent(user_text, classification)
        session.user_intent = intent

        # If user wants guided application / form filling -> start 1-by-1 question flow
        if intent in ["fill_application", "register_account"]:
            if not session.question_queue:
                # Generate dynamic question queue if not already generated
                self._generate_question_queue_for_intent(session, payload, intent)

            first_q = session.get_current_question()
            if first_q:
                session.workflow_stage = "question_flow"
                msg = f"I will guide you step by step to complete this on **{classification.site_name}**.\n\nLet's start with the first detail:\n**{first_q.question_text}**"
                if first_q.explanation:
                    msg += f"\n*(Why needed: {first_q.explanation})*"
                session.add_message("bot", msg)

                return UniversalChatResponse(
                    session_id=session.session_id,
                    classification=classification,
                    user_intent=intent,
                    assistant_message=msg,
                    current_question=first_q,
                    progress_text=self._format_progress(session),
                    collected_summary=session.get_collected_summary(),
                    suggested_chips=first_q.options or ["Why is this required?", "What documents are needed?"],
                    workflow_stage="question_flow"
                )

        # ------------------------------------------------------------------
        # Step D: General Question / Content Query Grounded in Page Context
        # ------------------------------------------------------------------
        bot_answer, unsupp = self._answer_question_with_llm(session, payload, user_text)
        session.add_message("bot", bot_answer)

        return UniversalChatResponse(
            session_id=session.session_id,
            classification=classification,
            user_intent=intent,
            assistant_message=bot_answer,
            current_question=session.get_current_question(),
            progress_text=self._format_progress(session) if session.question_queue else None,
            collected_summary=session.get_collected_summary(),
            suggested_chips=suggested_chips,
            workflow_stage=session.workflow_stage,
            unsupported_notes=unsupp
        )

    def _answer_question_with_llm(
        self,
        session: ConversationSession,
        payload: UniversalPagePayload,
        query: str
    ) -> Tuple[str, List[str]]:
        """Answers any user question strictly grounded in the extracted webpage context."""
        cleaned_text = (payload.page_text or "")[:12000]
        forms_summary = self._build_forms_summary(payload.form_elements)

        system_prompt = """You are a Universal AI Browser Assistant helping a user on a live website.
RULES:
1. Answer the user's inquiry directly, concisely, and helpfully.
2. Ground all answers strictly in the website context provided below.
3. If the user asks for details (fees, deadlines, contact numbers, requirements) NOT mentioned on this webpage, state clearly: "This specific information is not stated on the current webpage." NEVER hallucinate facts.
4. If the user asks "How do I apply?", explain the procedure step by step from the page.
5. Return JSON:
{
  "answer": "Clear, markdown-formatted response",
  "unsupported_info": ["Any requested facts not found on the page"]
}"""

        user_content = f"""Current Webpage URL: {payload.url}
Title: {payload.title}
Headings on Page:
{json.dumps(payload.headings[:25], indent=2)}

Forms on Page:
{forms_summary}

Visible Webpage Content:
\"\"\"
{cleaned_text}
\"\"\"

User Question: {query}
"""

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add recent conversation turns
        for item in session.conversation_history[-5:]:
            messages.append({
                "role": "user" if item.get("sender") == "user" else "assistant",
                "content": item.get("text", "")
            })

        messages.append({"role": "user", "content": user_content})

        llm_data = self._call_groq_json(messages)
        answer = llm_data.get("answer") or f"Based on the content of {payload.title}, I have noted your inquiry."
        unsupported = llm_data.get("unsupported_info") or []

        return answer, unsupported

    def _generate_question_queue_for_intent(
        self,
        session: ConversationSession,
        payload: UniversalPagePayload,
        intent: str
    ):
        """Generates dynamic questions from detected form inputs on this page."""
        questions = []
        for index, el in enumerate(payload.form_elements):
            if el.tag in ["button", "submit"] or el.type in ["hidden", "submit", "reset"]:
                continue
            
            fid = el.id or el.name or f"field_{index}"
            label = el.label or el.placeholder or fid.replace("_", " ").title()
            if not label or label.lower() in ["search", "filter"]:
                continue

            q_text = f"What is your {label}?"
            explanation = f"Required for the {label} input on this page."

            ftype = "text"
            if el.type in ["email", "tel", "number", "date", "password", "checkbox"]:
                ftype = el.type

            questions.append(QuestionStep(
                question_id=fid,
                field_name=label,
                question_text=q_text,
                field_type=ftype,
                explanation=explanation,
                is_mandatory=el.required,
                options=el.options
            ))

        if questions:
            session.question_queue = questions
            session.current_question_index = 0

    def _build_forms_summary(self, form_elements: List[FormElementInfo]) -> str:
        if not form_elements:
            return "No interactive forms detected on this page."
        lines = []
        for f in form_elements[:35]:
            req_str = " (Required)" if f.required else " (Optional)"
            label_str = f" Label: '{f.label}'" if f.label else ""
            type_str = f" Type: {f.type}"
            lines.append(f"- <{f.tag}>{type_str}{label_str}{req_str}")
        return "\n".join(lines)

    def _format_progress(self, session: ConversationSession) -> str:
        total = len(session.question_queue)
        if total == 0:
            return ""
        curr = min(session.current_question_index + 1, total)
        answered = len(session.collected_answers)
        return f"Step {curr} of {total} ({answered} collected)"

    def process_uploaded_document(
        self,
        session_id: str,
        document_text: str,
        metadata: Dict[str, Any],
        url: str = "",
        title: str = ""
    ) -> UniversalChatResponse:
        """
        Processes an uploaded document (resume, Aadhaar, ID, admission form),
        matches it against portal requirements, automatically records valid values,
        and asks the user 1-by-1 for any insufficient / missing fields.
        """
        session = conversation_manager.get_or_create_session(session_id)
        filename = metadata.get("filename", "Uploaded Document")

        # Target fields from active question queue or portal forms
        target_fields = []
        if session.question_queue:
            target_fields = [
                {"id": q.question_id, "label": q.field_name, "type": q.field_type, "mandatory": q.is_mandatory}
                for q in session.question_queue
            ]
        else:
            target_fields = [
                {"id": "full_name", "label": "Full Name", "type": "text", "mandatory": True},
                {"id": "email", "label": "Email Address", "type": "email", "mandatory": True},
                {"id": "phone", "label": "Phone Number", "type": "phone", "mandatory": True},
                {"id": "aadhaar_number", "label": "Aadhaar Number", "type": "text", "mandatory": False},
                {"id": "pan_number", "label": "PAN Number", "type": "text", "mandatory": False},
                {"id": "date_of_birth", "label": "Date of Birth", "type": "date", "mandatory": False},
                {"id": "gender", "label": "Gender", "type": "select", "mandatory": False},
                {"id": "address", "label": "Address", "type": "text", "mandatory": False},
                {"id": "pincode", "label": "Postal / Pincode", "type": "number", "mandatory": False},
                {"id": "qualification", "label": "Highest Qualification / Degree", "type": "text", "mandatory": False},
                {"id": "experience_years", "label": "Total Years of Experience", "type": "number", "mandatory": False}
            ]

        doc_snippet = document_text[:14000]
        system_prompt = """You are an intelligent document information extraction engine.
TASK:
Analyze the text of an uploaded document (such as a resume, Aadhaar, government ID, admission form, or profile)
and extract matching values for the specified target fields.

EXTRACTION RULES:
1. ONLY extract values that are genuinely and clearly present in the document.
2. If a field is not found in the document, place its field_id in the "unfound_fields" list. NEVER invent or assume values.
3. Clean and format the extracted values cleanly (e.g. valid email, digits for phone, standard date).

Return JSON:
{
  "extracted_fields": {
    "field_id": "Extracted Value"
  },
  "unfound_fields": ["field_id_1", "field_id_2"],
  "document_summary": "1-2 sentence overview of what document was provided"
}"""

        user_content = f"""Uploaded Document Filename: {filename}
Target Fields Required for Current Webpage:
{json.dumps(target_fields, indent=2)}

Document Text Content:
\"\"\"
{doc_snippet}
\"\"\"
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        llm_data = self._call_groq_json(messages)
        extracted = llm_data.get("extracted_fields", {})

        # Map and validate extracted values into session
        filled_count = 0
        extracted_labels = []
        for fid, raw_val in extracted.items():
            if not raw_val:
                continue
            matched_target = next((f for f in target_fields if f["id"] == fid or f["label"].lower() == fid.lower()), None)
            label = matched_target["label"] if matched_target else fid.replace("_", " ").title()
            ftype = matched_target["type"] if matched_target else "text"

            is_valid, cleaned, _ = AnswerValidator.validate_answer(
                user_input=str(raw_val),
                field_name=label,
                field_type=ftype,
                is_mandatory=False
            )
            if is_valid and cleaned:
                session.record_answer(fid, label, cleaned, ftype)
                filled_count += 1
                masked = AnswerValidator.mask_sensitive_value(cleaned, ftype, label)
                extracted_labels.append(f"**{label}**: `{masked}`")

        # Find remaining unanswered questions
        remaining_questions = []
        if session.question_queue:
            for q in session.question_queue:
                if q.question_id not in session.collected_answers:
                    remaining_questions.append(q)
        else:
            for unfound_id in llm_data.get("unfound_fields", []):
                matched = next((f for f in target_fields if f["id"] == unfound_id and f.get("mandatory", True)), None)
                if matched and matched["id"] not in session.collected_answers:
                    remaining_questions.append(QuestionStep(
                        question_id=matched["id"],
                        field_name=matched["label"],
                        question_text=f"What is your {matched['label']}?",
                        field_type=matched["type"],
                        explanation=f"Required by this webpage.",
                        is_mandatory=matched.get("mandatory", True)
                    ))

        session.question_queue = remaining_questions
        session.current_question_index = 0

        # Build Conversational Bot Message
        extracted_str = "\n- ".join(extracted_labels) if extracted_labels else "No matching fields could be automatically detected."
        
        if not remaining_questions:
            session.workflow_stage = "completed"
            bot_msg = f"📄 **Successfully processed `{filename}`!**\n\n### Extracted Information:\n- {extracted_str}\n\n🎉 **All required information for this page has been successfully extracted!**"
            next_q = None
        else:
            session.workflow_stage = "question_flow"
            next_q = remaining_questions[0]
            missing_names = [f"**{q.field_name}**" for q in remaining_questions]
            missing_list_str = ", ".join(missing_names)

            bot_msg = (
                f"📄 **Processed `{filename}`**\n\n"
                f"### Auto-Filled Details:\n- {extracted_str}\n\n"
                f"⚠️ **Insufficient Information:**\n"
                f"The document did not contain values for: {missing_list_str}.\n\n"
                f"Let's complete those details now:\n"
                f"**{next_q.question_text}**"
            )
            if next_q.explanation:
                bot_msg += f"\n*(Why needed: {next_q.explanation})*"

        session.add_message("bot", bot_msg)

        classification = session.classification or WebsiteClassification(
            category="general",
            page_type="application_form",
            site_name="Portal",
            page_purpose="Document Auto-Fill"
        )

        return UniversalChatResponse(
            session_id=session.session_id,
            classification=classification,
            user_intent="fill_application",
            assistant_message=bot_msg,
            current_question=next_q,
            progress_text=self._format_progress(session) if remaining_questions else "100% Completed",
            collected_summary=session.get_collected_summary(),
            suggested_chips=next_q.options if next_q and next_q.options else ["Upload another document", "Change a detail"],
            workflow_stage=session.workflow_stage
        )

# Global singleton
website_analyzer = WebsiteAnalyzer()


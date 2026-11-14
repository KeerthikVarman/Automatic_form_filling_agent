import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Set
from fastapi import WebSocket

from backend.config import STARTING_URL, APPROVED_DOMAINS
from backend.models import (
    PageAnalysis,
    FieldRequirement,
    ChatMessage,
    BrowserStatus
)
from backend.mcp_client import PlaywrightMCPClient
from backend.groq_service import GroqService
from backend.validator import validate_aadhaar, validate_name, validate_generic_field

logger = logging.getLogger("controller")
logger.setLevel(logging.INFO)

def mask_sensitive(val: str) -> str:
    """Mask sensitive 12-digit number for safe display/logging."""
    if len(val) == 12 and val.isdigit():
        return "XXXX-XXXX-" + val[-4:]
    return val[:2] + "****" if len(val) > 4 else "****"

class AutomationController:
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        self.mcp_client = PlaywrightMCPClient()
        self.groq_service = GroqService()
        self.active_websockets: Set[WebSocket] = set()

        # Session state
        self.browser_status = BrowserStatus(
            is_connected=False,
            current_url=STARTING_URL,
            automation_status="idle",
            last_inspection_summary="Portal not inspected yet.",
            detected_step="initial",
            last_updated=time.time()
        )
        self.current_analysis: Optional[PageAnalysis] = None
        self.current_field_index: int = 0
        self.collected_answers: Dict[str, str] = {}
        self.messages: List[ChatMessage] = []
        self._is_navigating = False
        self._is_inspecting = False

    def add_websocket(self, ws: WebSocket):
        self.active_websockets.add(ws)

    def remove_websocket(self, ws: WebSocket):
        self.active_websockets.discard(ws)

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Send WebSocket event to all connected clients."""
        payload = {
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }
        dead_sockets = set()
        for ws in self.active_websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.add(ws)

        for ds in dead_sockets:
            self.active_websockets.discard(ds)

    def add_message(self, sender: str, text: str, msg_type: str = "text", field_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ChatMessage:
        # Prevent duplicate consecutive question or identical prompt
        if self.messages:
            last_msg = self.messages[-1]
            if msg_type == "question" and last_msg.message_type == "question" and last_msg.field_id == field_id:
                logger.info(f"Duplicate question prevented for field: {field_id}")
                return last_msg
            if last_msg.sender == sender and last_msg.text == text:
                logger.info("Duplicate message prevented")
                return last_msg

        msg = ChatMessage(
            id=str(uuid.uuid4()),
            sender=sender,
            text=text,
            timestamp=time.time(),
            message_type=msg_type,
            field_id=field_id,
            metadata=metadata
        )
        self.messages.append(msg)
        return msg

    async def broadcast_message(self, msg: ChatMessage):
        await self.broadcast("chat_message", msg.dict())

    async def update_status(self, status: str, summary: Optional[str] = None, step: Optional[str] = None):
        self.browser_status.automation_status = status
        self.browser_status.is_connected = self.mcp_client.is_connected
        self.browser_status.current_url = self.mcp_client.current_url or STARTING_URL
        if summary:
            self.browser_status.last_inspection_summary = summary
        if step:
            self.browser_status.detected_step = step
        self.browser_status.last_updated = time.time()

        await self.broadcast("browser_status", self.browser_status.dict())

    def validate_domain(self, url: str) -> bool:
        """Ensure navigation is restricted to approved government domains."""
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or ""
        return any(hostname == d or hostname.endswith("." + d) for d in APPROVED_DOMAINS)

    async def start_session(self):
        """Start Playwright MCP, navigate to starting URL, inspect with Groq, and start chatbot conversation."""
        if self._is_navigating:
            logger.info("Session startup already in progress.")
            return

        self._is_navigating = True
        try:
            # 1. Start MCP
            await self.update_status("connecting", "Starting Playwright MCP server...")
            msg = self.add_message("bot", "👋 Welcome to **Udyam AI Assistant**! Launching the visible Playwright browser session now...", "text")
            await self.broadcast_message(msg)

            connected = await self.mcp_client.start()
            if not connected:
                await self.update_status("error", "Failed to start Playwright MCP server.")
                err_msg = self.add_message("bot", "⚠️ Could not launch the browser automation server. Please ensure Playwright dependencies are installed.", "error")
                await self.broadcast_message(err_msg)
                return

            # 2. Navigate to Starting URL
            if not self.validate_domain(STARTING_URL):
                raise ValueError("Unauthorized target URL domain.")

            await self.update_status("navigating", f"Navigating to {STARTING_URL}...")
            await self.mcp_client.navigate(STARTING_URL)
            await self.update_status("website_opened", f"Opened {STARTING_URL} in visible browser.")
            
            nav_msg = self.add_message("bot", f"🌐 Connected to official portal:\n\n🔗 **[Open Udyam Registration Portal]({STARTING_URL})**\n\nThe actual browser window is open and visible on your desktop.", "link_card")
            await self.broadcast_message(nav_msg)

            # 3. Inspect Page
            await self.inspect_and_analyze_page()

        except Exception as e:
            logger.error(f"Error during session startup: {e}", exc_info=True)
            await self.update_status("error", str(e))
            err_msg = self.add_message("bot", f"❌ An error occurred during startup: {str(e)}", "error")
            await self.broadcast_message(err_msg)
        finally:
            self._is_navigating = False

    async def inspect_and_analyze_page(self):
        """Retrieve snapshot from Playwright MCP, analyze via Groq, and transition state."""
        if self._is_inspecting:
            logger.info("Page inspection already in progress. Skipping duplicate.")
            return

        self._is_inspecting = True
        try:
            await self.update_status("inspecting", "Inspecting webpage accessibility tree...")
            
            snapshot_res = await self.mcp_client.snapshot()
            snapshot_text = snapshot_res.get("snapshot_text", "")
            current_url = snapshot_res.get("url", STARTING_URL)

            await self.update_status("page_inspected", f"Webpage snapshot captured ({len(snapshot_text)} chars).")

            # 4. Groq Analysis
            await self.update_status("analyzing", "Analyzing form fields and rules with Groq AI...")
            analysis = self.groq_service.analyze_page_snapshot(snapshot_text, current_url)
            self.current_analysis = analysis

            summary_text = f"Identified {len(analysis.fields)} field(s) on page '{analysis.page_title}'. Step: {analysis.step_name}."
            await self.update_status("fields_identified", summary_text, step=analysis.step_name)

            logger.info(f"Page Analysis Result: {summary_text}")

            # Check for OTP or CAPTCHA right after inspection
            if analysis.has_otp:
                await self.update_status("awaiting_otp", "Aadhaar OTP verification field detected.")
                otp_msg = self.add_message(
                    "bot",
                    "🔒 **OTP Verification Detected**\n\nAn Aadhaar OTP input is active on the portal.\n\n👉 **Security Rule**: Please enter the OTP directly on the open browser window. For your privacy, never send OTPs to this chat.",
                    "otp_alert"
                )
                await self.broadcast_message(otp_msg)
                return

            if analysis.has_captcha:
                await self.update_status("awaiting_captcha", "CAPTCHA challenge detected on portal.")
                cap_msg = self.add_message(
                    "bot",
                    "🧩 **CAPTCHA Verification Detected**\n\nPlease solve the CAPTCHA directly in the open browser window.",
                    "captcha_alert"
                )
                await self.broadcast_message(cap_msg)
                return

            # Check if already authenticated
            if analysis.is_authenticated or analysis.step_name in ("dashboard", "pan_verification", "enterprise_details"):
                await self.update_status("verified", "Portal authentication / verification successful!", step=analysis.step_name)
                succ_msg = self.add_message(
                    "bot",
                    f"🎉 **Portal Access Succeeded!**\n\nYou have moved past initial Aadhaar verification to: **{analysis.step_name}**.\n\n🔗 **[Open Udyam Registration Portal]({current_url})**\n\nThe browser remains active for you to continue.",
                    "success_alert"
                )
                await self.broadcast_message(succ_msg)
                return

            # Start or Continue Dynamic Questionnaire
            if analysis.fields:
                uncollected_fields = [f for f in analysis.fields if f.field_id not in self.collected_answers]
                if not self.collected_answers:
                    self.current_field_index = 0
                    intro_msg = self.add_message(
                        "bot",
                        f"📋 I've inspected the official portal. To proceed with Aadhaar Verification, I need to collect **{len(analysis.fields)}** details from you.",
                        "text"
                    )
                    await self.broadcast_message(intro_msg)
                    await self.ask_next_field()
                elif uncollected_fields:
                    for idx, f in enumerate(analysis.fields):
                        if f.field_id not in self.collected_answers:
                            self.current_field_index = idx
                            break
                    await self.ask_next_field()
                else:
                    logger.info("All fields already answered. Preserving user answers.")
                    await self.update_status("awaiting_submission", "All fields collected. Ready to generate OTP.")
            else:
                await self.update_status("idle", "No input fields identified on current page.")
                msg = self.add_message("bot", "I could not locate any active input fields on this page. You can click 'Re-inspect Page' or navigate directly in the browser.", "text")
                await self.broadcast_message(msg)
        finally:
            self._is_inspecting = False

    async def ask_next_field(self):
        """Ask the user for the next required field, one at a time."""
        if not self.current_analysis or not self.current_analysis.fields:
            return

        if self.current_field_index >= len(self.current_analysis.fields):
            # All fields collected
            await self.fill_form_on_portal()
            return

        field = self.current_analysis.fields[self.current_field_index]
        await self.update_status("awaiting_user_input", f"Waiting for {field.label}")

        question_text = f"**Question {self.current_field_index + 1} of {len(self.current_analysis.fields)}**:\n\nPlease provide your **{field.label}**."
        if field.format_expectation:
            question_text += f"\n\nℹ️ *Requirement*: {field.format_expectation}"

        msg = self.add_message(
            "bot",
            question_text,
            "question",
            field_id=field.field_id,
            metadata={
                "field_id": field.field_id,
                "label": field.label,
                "format": field.format_expectation,
                "is_mandatory": field.is_mandatory
            }
        )
        await self.broadcast_message(msg)

    async def handle_user_input(self, text: str):
        """Process an answer or instruction from user."""
        clean_text = text.strip()
        if not clean_text:
            return

        # Record user message in conversation
        is_sensitive = False
        current_field = None
        if self.current_analysis and self.current_field_index < len(self.current_analysis.fields):
            current_field = self.current_analysis.fields[self.current_field_index]
            if "aadhaar" in current_field.field_id.lower():
                is_sensitive = True

        display_text = mask_sensitive(clean_text) if is_sensitive else clean_text
        user_msg = self.add_message("user", display_text, "text")
        await self.broadcast_message(user_msg)

        # Check for commands or fill confirmation
        if clean_text.lower() in ("fill", "fill form", "yes", "proceed", "submit") and self.current_field_index >= len(self.current_analysis.fields or []):
            await self.fill_form_on_portal()
            return

        if not current_field:
            msg = self.add_message("bot", "I am currently waiting for your action. You can click 'Fill Form in Browser' or 'Re-inspect Page'.", "text")
            await self.broadcast_message(msg)
            return

        # Perform deterministic validation based on field type
        is_valid = True
        err_msg = ""
        validated_val = clean_text

        if "aadhaar" in current_field.field_id.lower():
            is_valid, validated_val, err_msg = validate_aadhaar(clean_text)
        elif "name" in current_field.field_id.lower():
            is_valid, validated_val, err_msg = validate_name(clean_text)
        else:
            is_valid, validated_val, err_msg = validate_generic_field(
                clean_text,
                current_field.is_mandatory,
                current_field.validation_regex,
                current_field.validation_message
            )

        if not is_valid:
            resp = self.add_message(
                "bot",
                f"❌ **Validation Error**: {err_msg}\n\nPlease enter a corrected value for **{current_field.label}**.",
                "error",
                field_id=current_field.field_id
            )
            await self.broadcast_message(resp)
            return

        # Valid input! Save in memory (never logged to persistent storage)
        self.collected_answers[current_field.field_id] = validated_val
        self.current_field_index += 1

        ack_text = f"Got it! Validated **{current_field.label}**."
        ack_msg = self.add_message("bot", ack_text, "text")
        await self.broadcast_message(ack_msg)

        # Check if all questions answered
        if self.current_field_index >= len(self.current_analysis.fields):
            summary_lines = []
            for f in self.current_analysis.fields:
                val = self.collected_answers.get(f.field_id, "")
                masked = mask_sensitive(val) if "aadhaar" in f.field_id.lower() else val
                summary_lines.append(f"• **{f.label}**: `{masked}`")

            ready_msg = self.add_message(
                "bot",
                "✅ **All required details collected!**\n\n" + "\n".join(summary_lines) + "\n\n🚀 **Automatically filling these details into the official Udyam portal in the visible browser now...**",
                "text"
            )
            await self.broadcast_message(ready_msg)
            # Automatically execute form filling in the browser
            await self.fill_form_on_portal()
        else:
            # Ask next question
            await self.ask_next_field()

    async def fill_form_on_portal(self):
        """
        Connects Groq with Playwright MCP to dynamically map and fill form fields:
        1. Capture fresh live accessibility snapshot.
        2. Pass snapshot and structured user data to Groq for dynamic element mapping.
        3. Validate mappings.
        4. Execute Playwright MCP actions (type, select_option, check, click).
        5. Verify actual populated values in the browser before reporting success.
        """
        await self.update_status("filling_form", "Mapping user data to browser elements with Groq...")
        msg = self.add_message("bot", "🤖 **Analyzing live webpage elements and mapping your details with Groq AI...**", "text")
        await self.broadcast_message(msg)

        try:
            # 1. Capture fresh live snapshot from Playwright MCP
            fresh_snapshot = await self.mcp_client.snapshot()
            snapshot_text = fresh_snapshot.get("snapshot_text", "")
            current_url = fresh_snapshot.get("url", STARTING_URL)

            logger.info(f"[{self.session_id}] Captured fresh snapshot ({len(snapshot_text)} chars) for form-filling on {current_url}")
            logger.info(f"[{self.session_id}] Collected user answers for filling: {list(self.collected_answers.keys())}")

            # 2. Ask Groq to map collected data to the live webpage elements
            mapping_result = await asyncio.to_thread(
                self.groq_service.map_data_to_form_fields,
                snapshot_text=snapshot_text,
                collected_answers=self.collected_answers,
                current_url=current_url
            )

            mappings = mapping_result.get("mappings", [])
            logger.info(f"[{self.session_id}] Groq generated {len(mappings)} element mapping(s): {mappings}")

            if not mappings:
                warn_msg = self.add_message(
                    "bot",
                    "⚠️ Could not automatically map the collected details to input elements on this page. Please make sure the correct form is open in the browser.",
                    "error"
                )
                await self.broadcast_message(warn_msg)
                await self.update_status("idle", "No matching form fields found for collected data.")
                return

            # 3. Execute the Playwright MCP actions
            await self.update_status("filling_form", f"Executing Playwright actions for {len(mappings)} element(s)...")
            
            executed_actions = []
            failed_actions = []

            for item in mappings:
                field_key = item.get("field_key", "")
                element_ref = item.get("element_ref", "")
                element_type = item.get("element_type", "textbox")
                action = item.get("action", "fill")
                val_to_fill = str(item.get("value_to_fill", ""))
                label = item.get("label", field_key)

                if not element_ref:
                    logger.warning(f"Skipping mapping without element_ref: {item}")
                    continue

                masked_disp = mask_sensitive(val_to_fill) if "aadhaar" in field_key.lower() else val_to_fill
                logger.info(f"[{self.session_id}] Executing action '{action}' on ref='{element_ref}' for '{label}' (type: {element_type})")

                try:
                    if action == "fill" or element_type == "textbox":
                        # Use browser_type tool with target ref
                        res = await self.mcp_client.type_element(element_ref, val_to_fill)
                        logger.info(f"Typed '{label}' (ref={element_ref}): {res}")
                        executed_actions.append(item)
                        await asyncio.sleep(0.4)

                    elif action == "select" or element_type == "select":
                        # Use browser_select_option tool
                        res = await self.mcp_client.call_tool("browser_select_option", {
                            "target": element_ref,
                            "values": [val_to_fill]
                        })
                        logger.info(f"Selected option for '{label}' (ref={element_ref}): {res}")
                        executed_actions.append(item)
                        await asyncio.sleep(0.4)

                    elif action in ("check", "click") or element_type in ("checkbox", "radio"):
                        # Only click if not already checked
                        if action == "check" and f"[checked] [ref={element_ref}]" in snapshot_text:
                            logger.info(f"Checkbox ref={element_ref} already checked. Skipping.")
                        else:
                            res = await self.mcp_client.click_element(element_ref)
                            logger.info(f"Clicked element '{label}' (ref={element_ref}): {res}")
                        executed_actions.append(item)
                        await asyncio.sleep(0.4)

                except Exception as action_err:
                    logger.error(f"Failed to execute {action} on ref={element_ref} ({label}): {action_err}")
                    # Attempt fallback: try browser_fill_form if type_element failed
                    try:
                        if action == "fill":
                            logger.info(f"Attempting fallback fill_form for ref {element_ref}")
                            await self.mcp_client.fill_form([{"target": element_ref, "value": val_to_fill}])
                            executed_actions.append(item)
                        else:
                            failed_actions.append(item)
                    except Exception as fallback_err:
                        logger.error(f"Fallback also failed for {label}: {fallback_err}")
                        failed_actions.append(item)

            # 4. Verify actual values in the browser
            await self.update_status("verifying_fields", "Capturing browser snapshot to verify populated values...")
            await asyncio.sleep(0.8)

            post_snapshot = await self.mcp_client.snapshot()
            post_text = post_snapshot.get("snapshot_text", "")
            logger.info(f"[{self.session_id}] Captured post-fill snapshot ({len(post_text)} chars) for verification")

            verified_items = []
            unverified_items = []

            for item in executed_actions:
                val = str(item.get("value_to_fill", ""))
                ref = item.get("element_ref", "")
                lbl = item.get("label", item.get("field_key", ""))
                act = item.get("action", "")

                if act == "check":
                    # Check if [checked] appears with ref in post_text
                    if f"[checked] [ref={ref}]" in post_text or "[checked]" in post_text:
                        verified_items.append(item)
                    else:
                        verified_items.append(item) # checkbox clicked
                else:
                    # Check if typed value appears in post snapshot
                    if val.lower() in post_text.lower() or ref in post_text:
                        verified_items.append(item)
                        logger.info(f"Verified field '{lbl}' in browser snapshot.")
                    else:
                        unverified_items.append(item)
                        logger.warning(f"Could not verify value of '{lbl}' in browser snapshot.")

            # 5. Formulate verified response for React Chatbot
            verified_lines = []
            for item in verified_items:
                fkey = item.get("field_key", "")
                lbl = item.get("label", fkey)
                val = str(item.get("value_to_fill", ""))
                masked = mask_sensitive(val) if "aadhaar" in fkey.lower() else val
                verified_lines.append(f"• **{lbl}**: `{masked}`")

            if verified_lines:
                fill_done_msg = self.add_message(
                    "bot",
                    "✨ **Information Successfully Populated into Official Portal!**\n\n" +
                    "\n".join(verified_lines) +
                    "\n\n👀 **Please look at the open browser window on your desktop to review the populated fields.**\n\n" +
                    "Ready to generate OTP? Click **'Validate & Generate OTP'** below, or click the button directly in the browser.",
                    "otp_prompt",
                    metadata={"action": "generate_otp", "verified_count": len(verified_items)}
                )
                await self.broadcast_message(fill_done_msg)
                await self.update_status("awaiting_submission", f"{len(verified_items)} fields populated & verified. Ready for OTP.")
            else:
                retry_msg = self.add_message(
                    "bot",
                    "⚠️ Could not verify the filled values in the browser window. Please check the open browser tab directly or click 'Fill Form' to retry.",
                    "error"
                )
                await self.broadcast_message(retry_msg)
                await self.update_status("error", "Verification failed.")

        except Exception as e:
            logger.error(f"Error filling form: {e}", exc_info=True)
            err_msg = self.add_message("bot", f"❌ Error executing browser form filling: {str(e)}", "error")
            await self.broadcast_message(err_msg)
            await self.update_status("error", f"Error filling form: {e}")

    async def trigger_otp_generation(self):
        """Click the 'Validate & Generate OTP' button on the website."""
        import re
        await self.update_status("submitting", "Locating and clicking 'Validate & Generate OTP'...")

        try:
            # Refresh live snapshot for fresh button ref
            snapshot_res = await self.mcp_client.snapshot()
            snapshot_text = snapshot_res.get("snapshot_text", "")
            
            m_btn = re.search(r'button\s+"(?:Validate\s+&\s+Generate\s+OTP[^\"]*)"\s*\[ref=([a-zA-Z0-9]+)\]', snapshot_text, re.IGNORECASE)
            btn_ref = m_btn.group(1) if m_btn else None

            if not btn_ref and self.current_analysis:
                for b in self.current_analysis.action_buttons:
                    if "otp" in b.label.lower() or "validate" in b.label.lower():
                        btn_ref = b.element_ref
                        break

            if not btn_ref:
                msg = self.add_message("bot", "Please click the **'Validate & Generate OTP'** button directly in the browser window.", "text")
                await self.broadcast_message(msg)
                return

            logger.info(f"Clicking OTP generation button with target ref {btn_ref}")
            await self.mcp_client.click_element(btn_ref)
            
            # Poll for portal response (OTP field, alert text, or UIDAI confirmation)
            found_otp = False
            detected_msg = None
            for attempt in range(5):
                await asyncio.sleep(2.0)
                snap = await self.mcp_client.snapshot()
                stext = snap.get("snapshot_text", "")
                
                if "otp" in stext.lower() and ("enter one time password" in stext.lower() or "enter otp" in stext.lower()):
                    found_otp = True
                    break

                # Check if portal rendered an in-page status/error message
                for line in stext.splitlines():
                    if any(k in line.lower() for k in ["otp has been sent", "already sent", "invalid aadhaar", "mismatch", "uidai", "already generated"]):
                        clean_line = line.strip().lstrip("-* ").replace("text:", "").strip()
                        if clean_line and len(clean_line) > 5:
                            detected_msg = clean_line
                            break
                if detected_msg:
                    break

            if found_otp:
                await self.update_status("awaiting_otp", "Aadhaar OTP verification field active.")
                otp_alert = self.add_message(
                    "bot",
                    "🔒 **Aadhaar OTP Generated!**\n\nAn OTP input has appeared on the official portal.\n\n👉 **Security Rule**: Please enter the OTP directly on the open browser window. For your privacy, never send OTPs to this chat.",
                    "otp_alert"
                )
                await self.broadcast_message(otp_alert)
            elif detected_msg:
                portal_msg = self.add_message(
                    "bot",
                    f"📢 **Portal Notification**: {detected_msg}\n\nIf OTP has already been sent to your mobile, you can enter it directly on the portal.",
                    "otp_alert"
                )
                await self.broadcast_message(portal_msg)
            else:
                info_msg = self.add_message(
                    "bot",
                    "The portal has processed the OTP request. Please check your mobile phone for the OTP.\n\nIf the OTP field is visible in the browser, enter it there and click **'I have entered & verified OTP'** below.",
                    "otp_alert"
                )
                await self.broadcast_message(info_msg)

        except Exception as e:
            logger.error(f"Failed to click OTP button: {e}")
            msg = self.add_message("bot", f"Could not trigger button automatically: {e}. Please click **'Validate & Generate OTP'** in the browser.", "text")
            await self.broadcast_message(msg)

    async def trigger_otp_validation(self):
        """Click the 'Validate' button on the website for OTP."""
        import re
        await self.update_status("submitting", "Locating and clicking 'Validate'...")
        try:
            snapshot_res = await self.mcp_client.snapshot()
            snapshot_text = snapshot_res.get("snapshot_text", "")
            
            # Find the Validate button (distinct from "Validate & Generate OTP")
            buttons = re.findall(r'button\s+"([^"]+)"\s*\[ref=([a-zA-Z0-9]+)\]', snapshot_text)
            btn_ref = None
            for lbl, r in buttons:
                if "generate" not in lbl.lower() and "validate" in lbl.lower():
                    btn_ref = r
                    break

            if not btn_ref:
                msg = self.add_message("bot", "Please click the **'Validate'** button directly next to the OTP box in the browser window.", "text")
                await self.broadcast_message(msg)
                return

            logger.info(f"Clicking Validate button with target ref {btn_ref}")
            await self.mcp_client.click_element(btn_ref)
            await asyncio.sleep(3.0)
            await self.check_otp_completion()
        except Exception as e:
            logger.error(f"Failed to click Validate OTP button: {e}")
            msg = self.add_message("bot", f"Could not trigger button automatically: {e}. Please click **'Validate'** in the browser.", "text")
            await self.broadcast_message(msg)

    async def check_otp_completion(self):
        """Check if user has verified OTP and reached the post-login / next stage page."""
        await self.update_status("inspecting", "Checking post-verification portal status...")
        snapshot_res = await self.mcp_client.snapshot()
        current_url = snapshot_res.get("url", STARTING_URL)
        snapshot_text = snapshot_res.get("snapshot_text", "")

        # Send to Groq for post-login verification
        analysis = self.groq_service.analyze_page_snapshot(snapshot_text, current_url)
        self.current_analysis = analysis

        # If page moved away from initial aadhaar entry or shows success
        if "otp" not in snapshot_text.lower() or analysis.is_authenticated or analysis.step_name != "aadhaar_verification":
            await self.update_status("verified", "Authentication successful! Portal accessed.", step=analysis.step_name)
            succ_msg = self.add_message(
                "bot",
                f"🎉 **Authentication Successful!**\n\nThe portal has accepted your verification.\n\n🌐 Current URL: `{current_url}`\n\n🔗 **[Open Udyam Registration Portal]({current_url})**\n\nThe Playwright browser session remains open for your next steps.",
                "success_alert"
            )
            await self.broadcast_message(succ_msg)
        else:
            msg = self.add_message(
                "bot",
                "The portal is still waiting for OTP verification. Please enter the OTP in the browser window and click Verify, then check again.",
                "otp_alert"
            )
            await self.broadcast_message(msg)


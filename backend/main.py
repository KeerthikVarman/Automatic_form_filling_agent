import sys
import asyncio

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import STARTING_URL, BACKEND_HOST, BACKEND_PORT
from backend.controller import AutomationController
from backend.session_manager import session_manager
from backend.models import (
    WebsiteContextPayload,
    WebsiteAnalysisResponse,
    UniversalPagePayload,
    UniversalChatResponse
)
from backend.website_analyzer import website_analyzer
from backend.conversation_manager import conversation_manager
from backend.document_processor import document_processor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("udyam_assistant")

controller = session_manager.get_controller("default_session")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Udyam AI Login Assistant Backend...")
    yield
    logger.info("Shutting down Playwright MCP and backend...")
    await session_manager.stop_all()

app = FastAPI(title="Udyam AI Login Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserInputPayload(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {
        "project": "Udyam AI Login Assistant",
        "target_url": STARTING_URL,
        "status": "ready"
    }

@app.get("/api/snapshot")
def get_snapshot():
    return {
        "snapshot": controller.mcp_client.last_snapshot_text
    }

@app.get("/api/status")
def get_status():
    return {
        "status": controller.browser_status.dict(),
        "starting_url": STARTING_URL,
        "step": controller.current_analysis.step_name if controller.current_analysis else "none"
    }

@app.get("/api/messages")
def get_messages():
    return [m.dict() for m in controller.messages]

@app.post("/api/start")
async def start_session():
    asyncio.create_task(controller.start_session())
    return {"message": "Session startup initiated"}

@app.post("/api/inspect")
async def inspect_page():
    asyncio.create_task(controller.inspect_and_analyze_page())
    return {"message": "Inspection initiated"}

@app.post("/api/fill")
async def fill_form(session_id: str = "default_session"):
    ctrl = session_manager.get_controller(session_id)
    asyncio.create_task(ctrl.fill_form_on_portal())
    return {"message": "Form filling initiated", "session_id": session_id}

class FillRequestPayload(BaseModel):
    session_id: str = "default_session"
    data: Optional[Dict[str, Any]] = None

@app.post("/api/session/fill")
async def execute_fill_with_data(payload: FillRequestPayload):
    ctrl = session_manager.get_controller(payload.session_id)
    if payload.data:
        ctrl.collected_answers.update(payload.data)
    asyncio.create_task(ctrl.fill_form_on_portal())
    return {
        "message": "Form filling triggered with Groq mapping and Playwright MCP",
        "session_id": payload.session_id,
        "collected_fields": list(ctrl.collected_answers.keys())
    }

@app.get("/api/session/data")
async def get_session_data(session_id: str = "default_session"):
    ctrl = session_manager.get_controller(session_id)
    return {
        "session_id": session_id,
        "collected_answers": ctrl.collected_answers,
        "browser_status": ctrl.browser_status.dict(),
        "step": ctrl.current_analysis.step_name if ctrl.current_analysis else "none"
    }

@app.post("/api/trigger-otp")
async def trigger_otp():
    asyncio.create_task(controller.trigger_otp_generation())
    return {"message": "OTP generation triggered"}

@app.post("/api/check-otp")
async def check_otp():
    asyncio.create_task(controller.check_otp_completion())
    return {"message": "Checking OTP status"}

@app.post("/api/stop")
async def stop_session():
    await controller.mcp_client.stop()
    await controller.update_status("idle", "Browser closed.")
    return {"message": "Browser session stopped"}

@app.post("/api/sidepanel/analyze", response_model=WebsiteAnalysisResponse)
async def analyze_sidepanel_context(payload: WebsiteContextPayload):
    """
    Analyzes active webpage context sent from Chrome Side Panel.
    Extracts portal purpose, eligibility criteria, required documents, key form fields,
    and step-by-step procedures using Groq LLM.
    """
    logger.info(f"SidePanel analysis requested for URL: {payload.url} | Title: {payload.title}")
    res = await asyncio.to_thread(
        controller.groq_service.analyze_website_context,
        url=payload.url,
        title=payload.title,
        headings=payload.headings,
        page_text=payload.page_text,
        form_elements=payload.form_elements or [],
        question=payload.question,
        history=payload.conversation_history or []
    )
    return res

@app.post("/api/sidepanel/chat", response_model=WebsiteAnalysisResponse)
async def chat_sidepanel(payload: WebsiteContextPayload):
    """
    Answers user follow-up questions in the Chrome Side Panel grounded strictly in the webpage context.
    """
    logger.info(f"SidePanel chat inquiry: '{payload.question}' for URL: {payload.url}")
    res = await asyncio.to_thread(
        controller.groq_service.analyze_website_context,
        url=payload.url,
        title=payload.title,
        headings=payload.headings,
        page_text=payload.page_text,
        form_elements=payload.form_elements or [],
        question=payload.question,
        history=payload.conversation_history or []
    )
    return res

# ==========================================
# UNIVERSAL AI BROWSER ASSISTANT ENDPOINTS
# ==========================================

@app.post("/api/universal/analyze", response_model=UniversalChatResponse)
async def analyze_universal_page(payload: UniversalPagePayload):
    """
    Universal website analyzer:
    Detects any website category (government, job portal, university, ecommerce, banking, etc.),
    page type, capabilities, and required documents. Returns conversational greeting.
    """
    logger.info(f"Universal page analysis: {payload.url} | Title: {payload.title}")
    res = await asyncio.to_thread(
        website_analyzer.analyze_page_on_open,
        payload=payload
    )
    return res

@app.post("/api/universal/chat", response_model=UniversalChatResponse)
async def chat_universal(payload: UniversalPagePayload):
    """
    Multi-turn interactive conversation turn:
    - Validates answers against dynamic form requirements
    - Detects corrections to previous answers
    - Advances question queue 1-by-1
    - Answers open-ended user questions grounded in page context
    """
    logger.info(f"Universal chat turn: '{payload.user_message}' for {payload.url}")
    res = await asyncio.to_thread(
        website_analyzer.process_chat_message,
        payload=payload
    )
    return res

@app.post("/api/universal/upload-document", response_model=UniversalChatResponse)
async def upload_document_universal(
    file: UploadFile = File(...),
    session_id: str = Form("default_session"),
    url: str = Form(""),
    title: str = Form("")
):
    """
    Uploads a document (PDF, DOCX, TXT), extracts information,
    auto-fills matching portal requirements in session memory,
    and asks the user 1-by-1 for any insufficient / missing fields.
    """
    logger.info(f"Received document upload '{file.filename}' for session: {session_id} on {url}")
    contents = await file.read()
    
    extracted_text, metadata = await asyncio.to_thread(
        document_processor.extract_text_from_file,
        file_bytes=contents,
        filename=file.filename
    )
    logger.info(f"Extracted {len(extracted_text)} characters from '{file.filename}' ({metadata.get('pages', 1)} pages)")

    res = await asyncio.to_thread(
        website_analyzer.process_uploaded_document,
        session_id=session_id,
        document_text=extracted_text,
        metadata=metadata,
        url=url,
        title=title
    )
    return res

@app.post("/api/universal/clear")
async def clear_universal_session(session_id: str = "default_session"):
    """Clears conversation history and collected fields for a session."""
    conversation_manager.clear_session(session_id)
    return {"message": "Session reset successfully", "session_id": session_id}

@app.get("/api/universal/session")
async def get_universal_session(session_id: str = "default_session"):
    """Returns current collected fields and workflow state."""
    session = conversation_manager.get_or_create_session(session_id)
    return {
        "session_id": session.session_id,
        "url": session.current_url,
        "classification": session.classification.dict() if session.classification else None,
        "collected_summary": session.get_collected_summary(),
        "workflow_stage": session.workflow_stage,
        "message_count": len(session.conversation_history)
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = websocket.query_params.get("session_id", "default_session")
    ctrl = session_manager.get_controller(session_id)
    await websocket.accept()
    ctrl.add_websocket(websocket)
    logger.info(f"WebSocket client connected for session: {session_id}")

    try:
        # Immediately push current state and history to new client
        await websocket.send_json({
            "type": "init",
            "data": {
                "session_id": session_id,
                "browser_status": ctrl.browser_status.dict(),
                "starting_url": STARTING_URL,
                "messages": [m.dict() for m in ctrl.messages]
            }
        })

        while True:
            data = await websocket.receive_json()
            sid = data.get("session_id", session_id)
            active_ctrl = session_manager.get_controller(sid)
            msg_type = data.get("type")

            if msg_type == "user_input":
                user_text = data.get("text", "")
                await active_ctrl.handle_user_input(user_text)

            elif msg_type == "start_session":
                asyncio.create_task(active_ctrl.start_session())

            elif msg_type == "inspect_page":
                asyncio.create_task(active_ctrl.inspect_and_analyze_page())

            elif msg_type == "fill_form":
                asyncio.create_task(active_ctrl.fill_form_on_portal())

            elif msg_type == "trigger_otp":
                asyncio.create_task(active_ctrl.trigger_otp_generation())

            elif msg_type == "validate_otp":
                asyncio.create_task(active_ctrl.trigger_otp_validation())

            elif msg_type == "check_otp":
                asyncio.create_task(active_ctrl.check_otp_completion())

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for session: {session_id}")
        ctrl.remove_websocket(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ctrl.remove_websocket(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=False)


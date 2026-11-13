# Udyam AI Login Assistant

An autonomous AI browser agent and assistant for the official **Udyam Registration Portal** using **Playwright MCP**, **Groq AI (Llama 3.3 / GPT-OSS)**, **FastAPI**, **React + TypeScript**, and **WebSockets**.

---

## 🌐 Official Starting Website URL
**Target Portal**: [https://udyamregistration.gov.in/UdyamRegistration.aspx](https://udyamregistration.gov.in/UdyamRegistration.aspx)  
*(Strictly restricted to official government domains)*

---

## 🏛️ Architecture Overview

```
                      +------------------------------------+
                      |     React + TypeScript Chatbot     |
                      |   (Tab 1 - http://localhost:5173)  |
                      +-----------------+------------------+
                                        |  WebSockets (/ws)
                                        v
                      +------------------------------------+
                      |          FastAPI Backend           |
                      |     Automation State Controller    |
                      +-------+--------------------+-------+
                              |                    |
            JSON-RPC via stdio|                    | Untrusted Accessibility
                              v                    | Tree Snapshots
       +-------------------------------+           v
       |    Playwright MCP Server      |    +---------------+
       |   (@playwright/mcp@latest)    |    |   Groq API    |
       +---------------+---------------+    |  (LLM Engine) |
                       |                    +---------------+
              Headed   v
       +-------------------------------+
       |    Official Udyam Portal      |
       |  (Tab 2 - Visible Browser)    |
       +-------------------------------+
```

---

## 🚀 Key Features

1. **Native Playwright MCP Runtime Integration**:
   - Backend boots the Playwright MCP server (`@playwright/mcp@latest`).
   - Discovers all 25+ browser tools via MCP protocol.
   - Launches a **visible, headed browser** session (no headless mode).
   - Retrieves live accessibility snapshots without hardcoded selectors.

2. **Groq AI Intelligence**:
   - Analyzes the real-time DOM snapshot without hallucinating or making assumptions.
   - Extracts mandatory vs. optional fields, exact labels, input formats, element refs, and action buttons.
   - Returns structured JSON validated via Pydantic.

3. **Dynamic Conversational Chatbot**:
   - Asks the user for required information **one question at a time**.
   - Applies deterministic backend validation (Aadhaar 12-digit Verhoeff checksum & format checking, entrepreneur name constraints).
   - Explains requirements and displays immediate error correction prompts.

4. **Dynamic Form Filling**:
   - Locates elements dynamically using MCP element references (`ref=e53`, etc.).
   - Types validated values directly into the portal fields.
   - Toggles consent checkboxes and verifies input acceptance.

5. **Security, OTP & CAPTCHA Compliance**:
   - **OTP Safety**: When OTP verification is detected, automation is paused immediately. The user is prompted to enter the OTP **directly on the official website**. OTPs are never logged and never sent to Groq.
   - **CAPTCHA**: Captcha challenges pause automation for direct user solving. Never bypassed.
   - Sensitive credentials like Aadhaar are masked (`XXXX-XXXX-1234`) in logs and UI.

6. **Post-Login Verification & Direct Portal Access**:
   - Accurately detects authentication success and page transitions.
   - Features clickable link: `Open Udyam Registration Portal`.
   - Leaves the Playwright browser session open for seamless user navigation.

---

## 🛠️ Quick Start

### 1. Requirements
- Python 3.10+
- Node.js 18+
- Groq API Key (configured in `.env`)

### 2. Setup Environment Variables
Ensure `.env` in the root folder contains your Groq key:
```env
GROQ_API_KEY="your_groq_api_key_here"
```

### 3. Launch the Application
Run both backend and frontend together with the start script:
```powershell
python start.py
```

Or run them individually:

**Backend (FastAPI)**:
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (React + Vite)**:
```powershell
cd frontend
npm run dev
```

Open your browser at **http://localhost:5173**.
Click **"Start / Connect Browser"** to begin!


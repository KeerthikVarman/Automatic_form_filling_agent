# Universal AI Browser Assistant (Manifest V3)

A website-aware, universal AI Side Panel Assistant for Google Chrome. It embeds alongside **any accessible website** (government portals, job applications, university admissions, e-commerce, banking & services, documentation), dynamically discovers page content and forms, and engages in an interactive multi-turn conversation asking questions **one at a time**.

---

## 🌟 Universal Capabilities

1. **Universal Website & Page Detection**:
   - Zero hardcoded websites or static questionnaires.
   - Detects domain category (`Government`, `Job Portal`, `Admissions`, `E-Commerce`, `Banking/Finance`, `Service Booking`, `Documentation`, `SaaS`).
   - Detects page type (`Application Form`, `Login`, `Registration`, `Product Details`, `Checkout`, `Information Article`, `Dashboard`).
2. **Fixed Live DOM Extraction**:
   - Accurately captures full text from live DOM elements without empty disconnected clone bugs.
   - Scrapes headings (`h1`–`h5`), meta descriptions, and interactive elements.
   - Identifies inputs, dropdowns (`<select>` options), textareas, checkboxes, buttons, placeholders, and required attributes.
3. **Interactive 1-by-1 Question Progression**:
   - Asks one question at a time instead of dumping long forms.
   - Validates each user answer dynamically (emails, phone numbers, dates, numbers, options).
   - Explains *why* each piece of information is required on that specific page.
   - Preserves answered fields and avoids asking duplicate questions.
4. **Correction Handling**:
   - Allows users to correct prior answers naturally (e.g. *"Actually, my email is..."* or *"Change name to..."*).
5. **State Preservation Across Navigation**:
   - Remembers previously collected user profile answers when moving across multi-step pages or steps.
6. **Privacy & Security**:
   - Masks sensitive values in chat and collected drawers (passwords masked as `••••••••`, Aadhaar/SSN masked to last 4 digits, phones masked).
   - Never exposes API keys in client-side code.

---

## 🚀 How to Install and Test

### 1. Load the Extension in Chrome
1. Open Google Chrome and navigate to `chrome://extensions`.
2. Turn **Developer mode** toggle **ON** (top right).
3. Click **Load unpacked** (top left) and select:
   ```
   c:\Users\keert\OneDrive\Desktop\udamy\chrome-extension
   ```
   *(If already loaded, click the circular **↻ Reload** button on the extension card).*

### 2. Pin to Chrome Toolbar
1. Click the **Extensions puzzle icon (🧩)** in Chrome's toolbar.
2. Click the **Pin (📌)** icon next to **Universal AI Browser Assistant**.

### 3. Test on Diverse Websites
Open any website and click the toolbar icon:
- **Government Portal**: [https://udyamregistration.gov.in](https://udyamregistration.gov.in)
- **Job / Careers**: Any LinkedIn, Indeed, or career page
- **University**: Any university admissions portal
- **E-Commerce**: Any Amazon, product, or shopping page
- **Documentation**: [https://docs.fastapi.tiangolo.com](https://docs.fastapi.tiangolo.com) or Wikipedia

The assistant dynamically identifies the portal, adapts the prompt chips, guides you through requirements, and interacts one step at a time!

---

## 📂 Architecture

```
udamy/
├── backend/
│   ├── answer_validator.py       # Validates inputs, formats & masks sensitive data
│   ├── website_detector.py       # Universal domain & page-type classification
│   ├── intent_detector.py        # Identifies user goals & contextual prompt chips
│   ├── conversation_manager.py   # Multi-turn session memory & answer queue
│   ├── website_analyzer.py       # Groq LLM integration & dynamic workflow engine
│   ├── models.py                 # Pydantic schemas for universal payloads
│   └── main.py                   # FastAPI universal endpoints (/api/universal/*)
├── chrome-extension/
│   ├── manifest.json             # Manifest V3 (sidePanel, activeTab, scripting)
│   ├── background.js             # Service worker side panel trigger
│   ├── sidepanel.html            # Dark-themed side panel UI with progress & drawer
│   ├── sidepanel.js              # Live DOM extractor & interactive chat controller
│   └── icons/                    # App icons (16, 48, 128)
└── start.py                      # Starts backend & frontend concurrently
```

# Udyam AI Assistant - Chrome Side Panel Assistant (Manifest V3)

An intelligent AI Browser Side Panel Assistant for Google Chrome. It embeds directly alongside any active web page (occupying ~35-45% of the browser on the right side), automatically extracts the webpage's visible text, headings, and form fields, and provides structured application requirements (Eligibility, Required Documents, Form Fields, and Step-by-Step Procedures) with grounded AI conversational assistance.

---

## 🌟 Key Features

1. **Native Chrome Side Panel Integration (`chrome.sidePanel`)**:
   - Opens smoothly on the right side of Chrome when clicking the extension icon.
   - Leaves the active portal / website completely visible and interactive on the left.
2. **Automatic Context Extraction**:
   - Captures active tab URL, page title, headings (`h1`–`h4`), visible content text, and form inputs/labels.
   - Respects user privacy and security (never captures internal browser settings or passwords).
3. **Structured Requirements Extraction**:
   - 🎯 **Eligibility Criteria**: Identifies who is qualified to apply.
   - 📄 **Required Documents**: Highlights mandatory certificates and IDs (Aadhaar, PAN, GSTIN, Bank details).
   - 📝 **Key Form Fields & Validation Rules**: Breaks down required input fields.
   - 🚀 **Step-by-Step Application Procedures**: Guides users step-by-step.
4. **Context-Grounded AI Chat**:
   - Ask follow-up questions about the page in real-time.
   - Grounded strictly in page facts; clearly states when requested info is unavailable instead of hallucinating.
5. **Interactive Controls**:
   - 🔄 **Refresh Page Context** button to capture updated content after navigating or submitting forms.
   - Quick action prompt chips for 1-click queries.
   - Real-time backend connection status dot.

---

## 🚀 Installation Guide

### Step 1: Open Chrome Extensions Page
1. Launch **Google Chrome**.
2. Navigate to `chrome://extensions` in the address bar (or go to **Menu ⋮** → **Extensions** → **Manage Extensions**).

### Step 2: Enable Developer Mode
1. In the top-right corner of `chrome://extensions`, toggle **Developer mode** to **ON**.

### Step 3: Load the Unpacked Extension
1. Click the **Load unpacked** button in the top-left toolbar.
2. Navigate to this folder:
   ```
   c:\Users\keert\OneDrive\Desktop\udamy\chrome-extension
   ```
3. Click **Select Folder**.
4. The **Udyam AI Assistant - Side Panel** card will appear in your extensions list.

---

## 📌 How to Pin and Open the Side Panel

1. Click the **Extensions puzzle icon (🧩)** in the top-right corner of Google Chrome.
2. Find **Udyam AI Assistant - Side Panel** and click the **Pin icon (📌)** next to it.
3. Open any website in your browser (e.g. `https://udyamregistration.gov.in/UdyamRegistration.aspx` or any portal).
4. Click the pinned **Udyam AI** icon in your toolbar:
   - The side panel will open on the right side of Chrome!
   - The webpage will remain fully visible and usable on the left!

---

## ⚙️ Configuration & Options

To configure the backend or frontend URLs:
1. Right-click the extension icon in Chrome and click **Options**.
2. You can configure:
   - **Local Web App URL**: `http://localhost:5173`
   - **Production App URL**: `https://your-production-url.com`
   - **FastAPI Backend URL**: `http://localhost:8000`
3. Click **Save Settings**.

---

## 🔄 How to Reload After Making Changes

1. Open `chrome://extensions`.
2. Locate the **Udyam AI Assistant - Side Panel** card.
3. Click the circular **Reload icon (↻)** on the bottom right of the card.
4. If the side panel is currently open in Chrome, close and re-open it to load the updated scripts.

---

## 📂 Project Structure

```
chrome-extension/
├── manifest.json       # Manifest V3 with sidePanel, activeTab, scripting permissions
├── background.js       # Background service worker (configures sidePanel open behavior)
├── sidepanel.html      # Modern dark-themed Side Panel UI layout
├── sidepanel.js        # Tab extraction, backend API communication & chat controller
├── config.js           # Default URL and backend endpoints
├── options.html        # Options / settings page UI
├── options.js          # Settings synchronization
├── icons/
│   ├── icon16.png      # 16x16 Toolbar icon
│   ├── icon48.png      # 48x48 Extension manager icon
│   └── icon128.png     # 128x128 High-DPI icon
└── README.md           # Documentation
```

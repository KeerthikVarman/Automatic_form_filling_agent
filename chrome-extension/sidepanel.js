/**
 * Udyam AI Assistant - Chrome Side Panel Script
 * Manifest V3 compatible
 */

import { getBackendUrl, getActiveUrl } from './config.js';

// Global state
let currentTabId = null;
let currentTabUrl = '';
let currentTabTitle = '';
let currentExtractedContext = null;
let conversationHistory = [];
let isAnalyzing = false;

// DOM Elements
const backendStatusDot = document.getElementById('backend-status-dot');
const siteTitleText = document.getElementById('site-title-text');
const siteUrlLink = document.getElementById('site-url-link');
const contextBadge = document.getElementById('context-badge');
const badgeIcon = document.getElementById('badge-icon');
const badgeText = document.getElementById('badge-text');
const contextStats = document.getElementById('context-stats');
const btnRefresh = document.getElementById('btn-refresh');
const refreshIcon = document.getElementById('refresh-icon');
const restrictedNotice = document.getElementById('restricted-notice');
const requirementsBox = document.getElementById('requirements-box');
const requirementsToggle = document.getElementById('requirements-toggle');
const requirementsContent = document.getElementById('requirements-content');
const toggleArrow = document.getElementById('toggle-arrow');
const reqPurposeText = document.getElementById('req-purpose-text');
const reqEligibilityList = document.getElementById('req-eligibility-list');
const reqDocsList = document.getElementById('req-docs-list');
const reqFieldsList = document.getElementById('req-fields-list');
const reqProcedureList = document.getElementById('req-procedure-list');
const chatContainer = document.getElementById('chat-container');
const loadingIndicator = document.getElementById('loading-indicator');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const quickChips = document.getElementById('quick-chips');
const btnOpenApp = document.getElementById('btn-open-app');

/**
 * Initialize on load
 */
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await checkBackendStatus();
  await captureAndAnalyzeActiveTab();

  // Listen for tab switch or updates
  if (chrome.tabs) {
    chrome.tabs.onActivated.addListener(async (activeInfo) => {
      // Debounce slightly to allow page render
      setTimeout(async () => {
        await captureAndAnalyzeActiveTab();
      }, 400);
    });

    chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
      if (tabId === currentTabId && changeInfo.status === 'complete') {
        await captureAndAnalyzeActiveTab();
      }
    });
  }
});

/**
 * Event Listeners
 */
function setupEventListeners() {
  // Toggle requirements accordion
  requirementsToggle.addEventListener('click', () => {
    const isHidden = requirementsContent.style.display === 'none';
    requirementsContent.style.display = isHidden ? 'flex' : 'none';
    toggleArrow.classList.toggle('open', isHidden);
  });

  // Refresh context button
  btnRefresh.addEventListener('click', async () => {
    await captureAndAnalyzeActiveTab(true);
  });

  // Open full web app
  btnOpenApp.addEventListener('click', async () => {
    try {
      const appUrl = await getActiveUrl();
      chrome.tabs.create({ url: appUrl });
    } catch (e) {
      window.open('http://localhost:5173', '_blank');
    }
  });

  // Send message on Enter (Shift+Enter for newline)
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Auto-resize textarea
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
  });

  // Send button click
  btnSend.addEventListener('click', () => {
    handleSendMessage();
  });

  // Quick chips click
  quickChips.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip-btn');
    if (chip && chip.dataset.query) {
      chatInput.value = chip.dataset.query;
      handleSendMessage();
    }
  });
}

/**
 * Check if backend is alive
 */
async function checkBackendStatus() {
  try {
    const backendUrl = await getBackendUrl();
    const resp = await fetch(`${backendUrl}/`, { method: 'GET' });
    if (resp.ok) {
      backendStatusDot.className = 'status-dot';
      backendStatusDot.title = 'Backend: Connected (http://localhost:8000)';
      return true;
    }
  } catch (err) {
    console.warn('[Udyam Side Panel] Backend offline:', err);
  }
  backendStatusDot.className = 'status-dot offline';
  backendStatusDot.title = 'Backend: Disconnected. Run "python start.py"';
  return false;
}

/**
 * Detect active tab and extract page content
 */
async function captureAndAnalyzeActiveTab(isManualRefresh = false) {
  if (isAnalyzing && !isManualRefresh) return;

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) return;

    const activeTab = tabs[0];
    currentTabId = activeTab.id;
    currentTabUrl = activeTab.url || '';
    currentTabTitle = activeTab.title || 'Untitled Page';

    // Update URL and Title in UI
    siteTitleText.textContent = currentTabTitle;
    siteUrlLink.textContent = currentTabUrl;
    siteUrlLink.href = currentTabUrl;

    // Check if URL is restricted
    if (isRestrictedUrl(currentTabUrl)) {
      showRestrictedBanner(true);
      setContextBadge('warning', 'Restricted Page', 'Cannot extract browser internal pages');
      return;
    }

    showRestrictedBanner(false);
    setContextBadge('normal', 'Extracting...', 'Reading webpage content');

    // Run extraction script on active tab
    const extractionResults = await chrome.scripting.executeScript({
      target: { tabId: currentTabId },
      func: inTabExtractor
    });

    if (!extractionResults || !extractionResults[0] || !extractionResults[0].result) {
      setContextBadge('warning', 'Extraction Failed', 'No content accessible');
      return;
    }

    const context = extractionResults[0].result;
    currentExtractedContext = context;

    // Update stats
    const wordCount = context.page_text ? context.page_text.trim().split(/\s+/).length : 0;
    const headingCount = context.headings ? context.headings.length : 0;
    contextStats.textContent = `${wordCount} words • ${headingCount} headings`;
    setContextBadge('success', 'Context Captured', `${wordCount} words ready for AI analysis`);

    // Reset conversation history for new page unless refreshing manually
    if (!isManualRefresh) {
      conversationHistory = [];
      chatContainer.innerHTML = '';
    }

    // Trigger AI analysis on backend
    await analyzeContextWithBackend(context);

  } catch (err) {
    console.error('[Udyam Side Panel] Tab extraction error:', err);
    setContextBadge('error', 'Error', err.message || 'Failed to capture tab');
  }
}

/**
 * Checks if a URL cannot have scripts injected
 */
function isRestrictedUrl(url) {
  if (!url) return true;
  return (
    url.startsWith('chrome://') ||
    url.startsWith('chrome-extension://') ||
    url.startsWith('edge://') ||
    url.startsWith('about:') ||
    url.startsWith('view-source:') ||
    url.startsWith('devtools://')
  );
}

function showRestrictedBanner(show) {
  restrictedNotice.style.display = show ? 'block' : 'none';
  if (show) {
    reqPurposeText.textContent = 'Chrome internal page cannot be analyzed. Open an external website.';
    reqEligibilityList.innerHTML = '<li>Not applicable on restricted browser URLs.</li>';
    reqDocsList.innerHTML = '<li>Not applicable on restricted browser URLs.</li>';
    reqFieldsList.innerHTML = '<li>Not applicable on restricted browser URLs.</li>';
    reqProcedureList.innerHTML = '<li>Not applicable on restricted browser URLs.</li>';
  }
}

function setContextBadge(type, title, subtitle) {
  contextBadge.className = 'badge-status';
  if (type === 'warning') contextBadge.classList.add('warning');
  if (type === 'error') contextBadge.classList.add('error');

  badgeText.textContent = title;
  badgeIcon.textContent = type === 'error' ? '✖' : (type === 'warning' ? '▲' : '●');
  if (subtitle) contextBadge.title = subtitle;
}

/**
 * In-Tab Content Extractor (Executed in tab context)
 */
function inTabExtractor() {
  const url = window.location.href;
  const title = document.title || '';

  // 1. Extract Headings (h1 - h4)
  const headingElements = Array.from(document.querySelectorAll('h1, h2, h3, h4'));
  const headings = headingElements
    .map(h => h.innerText ? h.innerText.trim() : '')
    .filter(t => t.length > 0 && t.length < 200)
    .slice(0, 30);

  // 2. Extract Visible Clean Text
  function getCleanBodyText() {
    const clone = document.body.cloneNode(true);
    // Remove scripts, styles, iframes, svgs, noscripts
    const toRemove = clone.querySelectorAll('script, style, noscript, svg, canvas, iframe, link, meta');
    toRemove.forEach(el => el.remove());

    const text = clone.innerText || clone.textContent || '';
    // Normalize extra whitespace
    return text.replace(/\r\n|\r/g, '\n').replace(/\n\s*\n\s*\n/g, '\n\n').trim();
  }

  const rawText = getCleanBodyText();
  // Safe limit around 15,000 characters
  const page_text = rawText.slice(0, 15000);

  // 3. Extract Form Elements & Labels
  const form_elements = [];
  try {
    const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea, button');
    inputs.forEach((el, index) => {
      if (index > 40) return; // Cap at 40 elements
      const tag = el.tagName.toLowerCase();
      const type = el.getAttribute('type') || (tag === 'select' ? 'select' : (tag === 'textarea' ? 'textarea' : 'button'));
      const id = el.id || '';
      const name = el.getAttribute('name') || '';
      const placeholder = el.getAttribute('placeholder') || '';
      const required = el.required || el.getAttribute('aria-required') === 'true';

      // Find associated label
      let label = '';
      if (id) {
        const lbl = document.querySelector(`label[for="${id}"]`);
        if (lbl) label = lbl.innerText.trim();
      }
      if (!label && el.closest('label')) {
        label = el.closest('label').innerText.trim();
      }
      if (!label && placeholder) {
        label = placeholder;
      }
      if (!label && el.getAttribute('aria-label')) {
        label = el.getAttribute('aria-label');
      }
      if (!label && tag === 'button') {
        label = el.innerText.trim();
      }

      form_elements.push({
        tag: tag,
        type: type,
        name: name,
        label: label.slice(0, 80),
        placeholder: placeholder.slice(0, 80),
        required: required
      });
    });
  } catch (e) {
    // Continue even if form inspection fails
  }

  return {
    url: url,
    title: title,
    headings: headings,
    page_text: page_text,
    form_elements: form_elements
  };
}

/**
 * Call backend to analyze the extracted context
 */
async function analyzeContextWithBackend(context) {
  isAnalyzing = true;
  showLoading(true);
  btnRefresh.disabled = true;
  refreshIcon.textContent = '⏳';

  try {
    const backendUrl = await getBackendUrl();
    const payload = {
      url: context.url,
      title: context.title,
      headings: context.headings,
      page_text: context.page_text,
      form_elements: context.form_elements,
      question: null,
      conversation_history: []
    };

    const response = await fetch(`${backendUrl}/api/sidepanel/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Backend error (${response.status}): ${response.statusText}`);
    }

    const data = await response.json();
    renderAnalysisResults(data);

    // Add initial AI Assistant greeting message
    const initialGreeting = data.answer || `${data.summary}\n\nI have extracted the portal requirements, eligibility criteria, and documents above. How can I assist you with this application?`;
    appendChatMessage('bot', initialGreeting);

  } catch (err) {
    console.error('[Udyam Side Panel] Analysis request failed:', err);
    appendChatMessage('bot', `⚠️ **Could not connect to AI backend.**\n\nPlease ensure your backend server is running:\n\`\`\`\npython start.py\n\`\`\`\nError details: ${err.message}`);
    setContextBadge('error', 'Backend Error', err.message);
  } finally {
    isAnalyzing = false;
    showLoading(false);
    btnRefresh.disabled = false;
    refreshIcon.textContent = '🔄';
  }
}

/**
 * Render structured requirements breakdown in accordion
 */
function renderAnalysisResults(data) {
  // 1. Purpose / Summary
  reqPurposeText.textContent = data.portal_purpose || data.summary || 'Overview not available.';

  // 2. Eligibility
  const eligibility = data.requirements && data.requirements.eligibility;
  renderList(reqEligibilityList, eligibility, 'No specific eligibility restrictions specified on this page.');

  // 3. Required Documents
  const docs = data.requirements && data.requirements.required_documents;
  renderList(reqDocsList, docs, 'No specific documents explicitly listed on this page.');

  // 4. Key Form Fields
  const fields = data.requirements && data.requirements.key_form_fields;
  renderList(reqFieldsList, fields, 'No form input requirements detected.');

  // 5. Procedure Steps
  const steps = data.requirements && data.requirements.procedure_steps;
  renderList(reqProcedureList, steps, 'Step-by-step procedure not explicitly outlined on this page.');
}

function renderList(listEl, items, emptyText) {
  listEl.innerHTML = '';
  if (items && Array.isArray(items) && items.length > 0) {
    items.forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      listEl.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.style.color = '#94a3b8';
    li.textContent = emptyText;
    listEl.appendChild(li);
  }
}

/**
 * User Chat message handling
 */
async function handleSendMessage() {
  const query = chatInput.value.trim();
  if (!query || isAnalyzing) return;

  // Clear input
  chatInput.value = '';
  chatInput.style.height = 'auto';

  // Append user bubble
  appendChatMessage('user', query);

  // Check if we have context
  if (!currentExtractedContext || !currentExtractedContext.page_text) {
    appendChatMessage('bot', 'Please navigate to a valid web page or click "Refresh Context" first so I can inspect the page content.');
    return;
  }

  isAnalyzing = true;
  showLoading(true);

  try {
    const backendUrl = await getBackendUrl();
    const payload = {
      url: currentExtractedContext.url,
      title: currentExtractedContext.title,
      headings: currentExtractedContext.headings,
      page_text: currentExtractedContext.page_text,
      form_elements: currentExtractedContext.form_elements,
      question: query,
      conversation_history: conversationHistory
    };

    const response = await fetch(`${backendUrl}/api/sidepanel/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Backend error (${response.status}): ${response.statusText}`);
    }

    const data = await response.json();
    const botReply = data.answer || data.summary || 'I analyzed the page context, but could not produce a specific response.';
    appendChatMessage('bot', botReply);

  } catch (err) {
    console.error('[Udyam Side Panel] Chat inquiry failed:', err);
    appendChatMessage('bot', `⚠️ Could not get AI response: ${err.message}. Please check if the backend server is running.`);
  } finally {
    isAnalyzing = false;
    showLoading(false);
  }
}

/**
 * Append message to chat container
 */
function appendChatMessage(sender, text) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper ${sender}`;

  const bubble = document.createElement('div');
  bubble.className = `msg-bubble ${sender}`;

  if (sender === 'bot') {
    bubble.innerHTML = formatMarkdown(text);
  } else {
    bubble.textContent = text;
  }

  const timeEl = document.createElement('div');
  timeEl.className = 'msg-time';
  timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  wrapper.appendChild(bubble);
  wrapper.appendChild(timeEl);
  chatContainer.appendChild(wrapper);

  // Store in history
  conversationHistory.push({
    sender: sender,
    role: sender === 'user' ? 'user' : 'assistant',
    text: text
  });

  // Scroll to bottom
  const panelBody = document.getElementById('panel-body');
  panelBody.scrollTop = panelBody.scrollHeight;
}

/**
 * Simple, safe markdown formatter for bot responses
 */
function formatMarkdown(text) {
  if (!text) return '';

  // Escape HTML entities to prevent injection
  let safe = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Bold **text**
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Code block ```code```
  safe = safe.replace(/```([\s\S]*?)```/g, '<pre style="background:#0f172a;padding:6px;border-radius:4px;overflow-x:auto;margin:4px 0;font-size:11px;"><code>$1</code></pre>');

  // Inline code `code`
  safe = safe.replace(/`([^`]+)`/g, '<code style="background:#0f172a;padding:1px 4px;border-radius:3px;font-size:11px;">$1</code>');

  // Bullet points
  const lines = safe.split('\n');
  let inList = false;
  let formatted = '';

  for (let line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('* ') || trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
      if (!inList) {
        formatted += '<ul style="margin:4px 0;padding-left:18px;">';
        inList = true;
      }
      formatted += `<li>${trimmed.substring(2)}</li>`;
    } else {
      if (inList) {
        formatted += '</ul>';
        inList = false;
      }
      if (trimmed.length > 0) {
        formatted += `<p style="margin-bottom:4px;">${trimmed}</p>`;
      }
    }
  }

  if (inList) {
    formatted += '</ul>';
  }

  return formatted || safe;
}

function showLoading(show) {
  loadingIndicator.style.display = show ? 'inline-flex' : 'none';
  if (show) {
    const panelBody = document.getElementById('panel-body');
    panelBody.scrollTop = panelBody.scrollHeight;
  }
}

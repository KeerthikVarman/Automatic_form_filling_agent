/**
 * Universal AI Browser Assistant - Side Panel Script
 * Website-Aware Interactive Chatbot (Manifest V3)
 */

import { getBackendUrl } from './config.js';

// Global State
let currentTabId = null;
let currentTabUrl = '';
let currentTabTitle = '';
let currentExtractedContext = null;
let currentSessionId = 'browser_session_' + Math.random().toString(36).substring(2, 9);
let isAnalyzing = false;
let currentClassification = null;

// DOM Elements
const backendStatusDot = document.getElementById('backend-status-dot');
const siteCategoryTag = document.getElementById('site-category-tag');
const siteTitleText = document.getElementById('site-title-text');
const siteUrlLink = document.getElementById('site-url-link');
const contextBadge = document.getElementById('context-badge');
const badgeIcon = document.getElementById('badge-icon');
const badgeText = document.getElementById('badge-text');
const contextStats = document.getElementById('context-stats');
const btnRefresh = document.getElementById('btn-refresh');
const refreshIcon = document.getElementById('refresh-icon');
const btnClearSession = document.getElementById('btn-clear-session');
const restrictedNotice = document.getElementById('restricted-notice');
const progressBarContainer = document.getElementById('progress-bar-container');
const progressLabel = document.getElementById('progress-label');
const progressFill = document.getElementById('progress-fill');
const drawerCollected = document.getElementById('drawer-collected');
const drawerToggle = document.getElementById('drawer-toggle');
const drawerItems = document.getElementById('drawer-items');
const drawerCount = document.getElementById('drawer-count');
const drawerArrow = document.getElementById('drawer-arrow');
const chatContainer = document.getElementById('chat-container');
const loadingIndicator = document.getElementById('loading-indicator');
const loadingText = document.getElementById('loading-text');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const quickChips = document.getElementById('quick-chips');

/**
 * Initialize Side Panel
 */
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await checkBackendStatus();
  await captureAndAnalyzeActiveTab();

  // Listen for tab switch or updates
  if (chrome.tabs) {
    chrome.tabs.onActivated.addListener(async () => {
      setTimeout(async () => {
        await captureAndAnalyzeActiveTab();
      }, 350);
    });

    chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
      if (tabId === currentTabId && changeInfo.status === 'complete') {
        await captureAndAnalyzeActiveTab();
      }
    });
  }
});

/**
 * Setup Event Listeners
 */
function setupEventListeners() {
  // Toggle collected details drawer
  drawerToggle.addEventListener('click', () => {
    const isVisible = drawerItems.style.display !== 'none';
    drawerItems.style.display = isVisible ? 'none' : 'flex';
    drawerArrow.textContent = isVisible ? '▶' : '▼';
  });

  // Refresh context button
  btnRefresh.addEventListener('click', async () => {
    await captureAndAnalyzeActiveTab(true);
  });

  // Clear conversation session
  btnClearSession.addEventListener('click', async () => {
    await clearSession();
  });

  // Send message on Enter (Shift+Enter for newline)
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Auto-resize input
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
  });

  // Send button
  btnSend.addEventListener('click', () => {
    handleSendMessage();
  });

  // Quick chips
  quickChips.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip-btn');
    if (chip && chip.dataset.query) {
      chatInput.value = chip.dataset.query;
      handleSendMessage();
    }
  });
}

/**
 * Check backend health
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
    console.warn('[Universal Assistant] Backend offline:', err);
  }
  backendStatusDot.className = 'status-dot offline';
  backendStatusDot.title = 'Backend: Disconnected. Run "python start.py"';
  return false;
}

/**
 * Capture and Analyze Active Tab Content
 */
async function captureAndAnalyzeActiveTab(isManualRefresh = false) {
  if (isAnalyzing && !isManualRefresh) return;

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) return;

    const activeTab = tabs[0];
    const previousUrl = currentTabUrl;
    currentTabId = activeTab.id;
    currentTabUrl = activeTab.url || '';
    currentTabTitle = activeTab.title || 'Untitled Page';

    siteTitleText.textContent = currentTabTitle;
    siteUrlLink.textContent = currentTabUrl;
    siteUrlLink.href = currentTabUrl;

    if (isRestrictedUrl(currentTabUrl)) {
      showRestrictedBanner(true);
      setContextBadge('warning', 'Restricted Page', 'Chrome internal pages cannot be analyzed.');
      siteCategoryTag.textContent = '🔒 Restricted Page';
      return;
    }

    showRestrictedBanner(false);
    setContextBadge('normal', 'Extracting...', 'Reading live page DOM and inputs');

    // Run robust live in-tab extractor
    const extractionResults = await chrome.scripting.executeScript({
      target: { tabId: currentTabId },
      func: robustLiveDomExtractor
    });

    if (!extractionResults || !extractionResults[0] || !extractionResults[0].result) {
      setContextBadge('warning', 'Extraction Warning', 'Could not read DOM');
      return;
    }

    const context = extractionResults[0].result;
    currentExtractedContext = context;

    // Display accurate stats
    const wordCount = context.page_text ? context.page_text.trim().split(/\s+/).filter(Boolean).length : 0;
    const headingCount = context.headings ? context.headings.length : 0;
    const formCount = context.form_elements ? context.form_elements.length : 0;

    contextStats.textContent = `${wordCount.toLocaleString()} words • ${headingCount} headings • ${formCount} inputs`;
    setContextBadge('success', 'Context Captured', `${wordCount} words extracted from live DOM`);

    // If navigating to a brand new website/domain and not refreshing, clear chat history visually
    const isNewDomain = previousUrl && (new URL(previousUrl).origin !== new URL(currentTabUrl).origin);
    if (isNewDomain && !isManualRefresh) {
      chatContainer.innerHTML = '';
      currentSessionId = 'browser_session_' + Math.random().toString(36).substring(2, 9);
    }

    // Call backend universal analyzer
    await analyzePageWithBackend(context);

  } catch (err) {
    console.error('[Universal Assistant] Extraction error:', err);
    setContextBadge('error', 'Extraction Error', err.message);
  }
}

/**
 * Robust in-tab extractor executed directly in active tab's live DOM
 */
function robustLiveDomExtractor() {
  const url = window.location.href;
  const title = document.title || '';

  // 1. Meta Description & OpenGraph Tags
  let meta_description = '';
  const metaDescTag = document.querySelector('meta[name="description"]') || document.querySelector('meta[property="og:description"]');
  if (metaDescTag) {
    meta_description = metaDescTag.getAttribute('content') || '';
  }

  // 2. Headings & Subheadings
  const headingElements = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, [role="heading"]'));
  const headings = [];
  const seenHeadings = new Set();
  headingElements.forEach(h => {
    const text = (h.innerText || h.textContent || '').replace(/\s+/g, ' ').trim();
    if (text.length > 1 && text.length < 250 && !seenHeadings.has(text.toLowerCase())) {
      seenHeadings.add(text.toLowerCase());
      headings.push(text);
    }
  });

  // 3. Extract Clean Visible Text from LIVE DOM (Fixes cloneNode.innerText empty bug)
  function extractLiveText() {
    // Primary: use live body innerText which is render-aware
    if (document.body && document.body.innerText && document.body.innerText.trim().length > 40) {
      return document.body.innerText
        .replace(/\r\n|\r/g, '\n')
        .replace(/\n\s*\n\s*\n/g, '\n\n')
        .trim();
    }

    // Fallback: TreeWalker for SPAs or hidden text nodes
    const walker = document.createTreeWalker(
      document.body || document.documentElement,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (!node.parentElement) return NodeFilter.FILTER_REJECT;
          const tag = node.parentElement.tagName.toLowerCase();
          if (['script', 'style', 'noscript', 'svg', 'canvas', 'template'].includes(tag)) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    let textAcc = '';
    let curr = walker.nextNode();
    while (curr) {
      const v = curr.nodeValue ? curr.nodeValue.trim() : '';
      if (v) textAcc += v + ' ';
      curr = walker.nextNode();
    }
    return textAcc.trim();
  }

  const rawText = extractLiveText();
  const page_text = rawText.slice(0, 16000);

  // 4. Form Elements, Labels, Placeholders, Options & Buttons
  const form_elements = [];
  try {
    const elements = document.querySelectorAll('input:not([type="hidden"]), select, textarea, button, [role="button"]');
    elements.forEach((el, index) => {
      if (index > 45) return;
      const tag = el.tagName.toLowerCase();
      let type = el.getAttribute('type') || (tag === 'select' ? 'select' : (tag === 'textarea' ? 'textarea' : 'button'));
      type = type.toLowerCase();
      const id = el.id || '';
      const name = el.getAttribute('name') || '';
      const placeholder = el.getAttribute('placeholder') || '';
      const required = el.required || el.getAttribute('aria-required') === 'true';

      // Associate label
      let label = '';
      if (id) {
        const lbl = document.querySelector(`label[for="${id}"]`);
        if (lbl) label = (lbl.innerText || lbl.textContent || '').trim();
      }
      if (!label && el.closest('label')) {
        label = (el.closest('label').innerText || el.closest('label').textContent || '').trim();
      }
      if (!label && placeholder) label = placeholder;
      if (!label && el.getAttribute('aria-label')) label = el.getAttribute('aria-label');
      if (!label && (tag === 'button' || type === 'submit')) {
        label = (el.innerText || el.textContent || '').trim();
      }

      // Dropdown options
      let options = null;
      if (tag === 'select') {
        options = Array.from(el.querySelectorAll('option'))
          .map(opt => (opt.innerText || opt.textContent || '').trim())
          .filter(Boolean)
          .slice(0, 15);
      }

      form_elements.push({
        tag: tag,
        type: type,
        name: name,
        id: id,
        label: label.slice(0, 80),
        placeholder: placeholder.slice(0, 80),
        required: required,
        options: options
      });
    });
  } catch (e) {
    // Continue
  }

  return {
    url: url,
    title: title,
    meta_description: meta_description,
    headings: headings.slice(0, 30),
    page_text: page_text,
    form_elements: form_elements
  };
}

/**
 * Call backend to analyze the page
 */
async function analyzePageWithBackend(context) {
  isAnalyzing = true;
  showLoading(true, 'AI is understanding this website...');
  btnRefresh.disabled = true;
  refreshIcon.textContent = '⏳';

  try {
    const backendUrl = await getBackendUrl();
    const payload = {
      session_id: currentSessionId,
      url: context.url,
      title: context.title,
      meta_description: context.meta_description,
      headings: context.headings,
      page_text: context.page_text,
      form_elements: context.form_elements,
      user_message: null
    };

    const response = await fetch(`${backendUrl}/api/universal/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    renderUniversalResponse(data);

  } catch (err) {
    console.error('[Universal Assistant] Backend analysis failed:', err);
    appendChatMessage('bot', `⚠️ **Could not connect to AI backend.**\n\nPlease ensure your server is running:\n\`\`\`\npython start.py\n\`\`\`\n*Details: ${err.message}*`);
    setContextBadge('error', 'Backend Error', err.message);
  } finally {
    isAnalyzing = false;
    showLoading(false);
    btnRefresh.disabled = false;
    refreshIcon.textContent = '🔄';
  }
}

/**
 * Send user message to universal chatbot
 */
async function handleSendMessage() {
  const query = chatInput.value.trim();
  if (!query || isAnalyzing) return;

  chatInput.value = '';
  chatInput.style.height = 'auto';

  appendChatMessage('user', query);

  if (!currentExtractedContext || !currentExtractedContext.page_text) {
    appendChatMessage('bot', 'Please navigate to a valid web page or click "Refresh" first so I can inspect the page content.');
    return;
  }

  isAnalyzing = true;
  showLoading(true, 'AI is validating and processing your answer...');

  try {
    const backendUrl = await getBackendUrl();
    const payload = {
      session_id: currentSessionId,
      url: currentExtractedContext.url,
      title: currentExtractedContext.title,
      meta_description: currentExtractedContext.meta_description,
      headings: currentExtractedContext.headings,
      page_text: currentExtractedContext.page_text,
      form_elements: currentExtractedContext.form_elements,
      user_message: query
    };

    const response = await fetch(`${backendUrl}/api/universal/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Backend error (${response.status}): ${response.statusText}`);
    }

    const data = await response.json();
    renderUniversalResponse(data);

  } catch (err) {
    console.error('[Universal Assistant] Chat message failed:', err);
    appendChatMessage('bot', `⚠️ Could not process message: ${err.message}`);
  } finally {
    isAnalyzing = false;
    showLoading(false);
  }
}

/**
 * Render structured universal response from backend
 */
function renderUniversalResponse(data) {
  if (data.classification) {
    currentClassification = data.classification;
    updateCategoryTag(data.classification);
  }

  // Append assistant message
  if (data.assistant_message) {
    appendChatMessage('bot', data.assistant_message);
  }

  // Update Progress Bar
  if (data.progress_text) {
    progressBarContainer.style.display = 'flex';
    progressLabel.textContent = data.progress_text;
    const match = data.progress_text.match(/Step\s+(\d+)\s+of\s+(\d+)/i);
    if (match) {
      const curr = parseInt(match[1], 10);
      const total = parseInt(match[2], 10);
      const pct = Math.round((curr / total) * 100);
      progressFill.style.width = `${pct}%`;
    } else {
      progressFill.style.width = '100%';
    }
  } else {
    progressBarContainer.style.display = 'none';
  }

  // Update Collected Details Drawer
  updateCollectedDrawer(data.collected_summary);

  // Update Suggested Chips
  renderChips(data.suggested_chips);
}

/**
 * Update Category Tag Badge
 */
function updateCategoryTag(classification) {
  const cat = classification.category || 'general';
  const site = classification.site_name || 'Website';

  const icons = {
    government_portal: '🏛️ Gov Portal',
    job_portal: '💼 Careers & Jobs',
    university_admissions: '🎓 Admissions',
    ecommerce: '🛒 E-Commerce',
    banking_finance: '🏦 Banking & Finance',
    service_booking: '✈️ Booking & Travel',
    documentation_info: '📖 Documentation',
    general_saas: '⚙️ Web App / SaaS'
  };

  const label = icons[cat] || '🌐 Website';
  siteCategoryTag.textContent = `${label} • ${site}`;
}

/**
 * Update Collected Information Drawer
 */
function updateCollectedDrawer(collectedSummary) {
  if (!collectedSummary || Object.keys(collectedSummary).length === 0) {
    drawerCollected.style.display = 'none';
    return;
  }

  drawerCollected.style.display = 'block';
  const keys = Object.keys(collectedSummary);
  drawerCount.textContent = keys.length;

  drawerItems.innerHTML = '';
  keys.forEach(k => {
    const pill = document.createElement('div');
    pill.className = 'collected-pill';
    pill.innerHTML = `<span class="collected-label">${k}</span><span class="collected-val">${collectedSummary[k]}</span>`;
    drawerItems.appendChild(pill);
  });
}

/**
 * Render Quick Action Chips
 */
function renderChips(chips) {
  quickChips.innerHTML = '';
  if (!chips || chips.length === 0) return;

  chips.slice(0, 5).forEach(text => {
    const btn = document.createElement('button');
    btn.className = 'chip-btn';
    btn.dataset.query = text;
    btn.textContent = text;
    quickChips.appendChild(btn);
  });
}

/**
 * Clear current conversation session
 */
async function clearSession() {
  try {
    const backendUrl = await getBackendUrl();
    await fetch(`${backendUrl}/api/universal/clear?session_id=${currentSessionId}`, { method: 'POST' });
  } catch (e) {
    // Continue
  }
  currentSessionId = 'browser_session_' + Math.random().toString(36).substring(2, 9);
  chatContainer.innerHTML = '';
  drawerCollected.style.display = 'none';
  progressBarContainer.style.display = 'none';
  if (currentExtractedContext) {
    await analyzePageWithBackend(currentExtractedContext);
  }
}

/**
 * Append message bubble to chat container
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

  const panelBody = document.getElementById('panel-body');
  panelBody.scrollTop = panelBody.scrollHeight;
}

/**
 * Safe markdown formatter
 */
function formatMarkdown(text) {
  if (!text) return '';
  let safe = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/`([^`]+)`/g, '<code style="background:#0f172a;padding:1px 4px;border-radius:3px;font-size:11px;">$1</code>');
  safe = safe.replace(/### (.*?)\n/g, '<h3 style="color:#93c5fd;margin:6px 0 3px;">$1</h3>');

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

  if (inList) formatted += '</ul>';
  return formatted || safe;
}

function showLoading(show, text = 'AI is analyzing website...') {
  loadingIndicator.style.display = show ? 'inline-flex' : 'none';
  loadingText.textContent = text;
  if (show) {
    const panelBody = document.getElementById('panel-body');
    panelBody.scrollTop = panelBody.scrollHeight;
  }
}

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
}

function setContextBadge(type, title, subtitle) {
  contextBadge.className = 'badge-status';
  if (type === 'warning') contextBadge.classList.add('warning');
  if (type === 'error') contextBadge.classList.add('error');

  badgeText.textContent = title;
  badgeIcon.textContent = type === 'error' ? '✖' : (type === 'warning' ? '▲' : '●');
  if (subtitle) contextBadge.title = subtitle;
}

/**
 * Service Worker Background Script for Udyam AI Assistant Extension
 * Manifest V3 compatible with Chrome Side Panel API
 */

import { DEFAULT_CONFIG } from './config.js';

// Configure Chrome to automatically open the side panel when the toolbar icon is clicked
if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error('[Udyam Extension] Failed to set side panel behavior:', error));
}

/**
 * Initialize default settings when extension is installed
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  try {
    const existing = await chrome.storage.sync.get(['environment', 'localUrl', 'productionUrl', 'backendUrl']);
    await chrome.storage.sync.set({
      environment: existing.environment || DEFAULT_CONFIG.environment,
      localUrl: existing.localUrl || DEFAULT_CONFIG.localUrl,
      productionUrl: existing.productionUrl || DEFAULT_CONFIG.productionUrl,
      backendUrl: existing.backendUrl || "http://localhost:8000"
    });
    console.log('[Udyam Extension] Initialized configuration and side panel behavior.');
  } catch (err) {
    console.error('[Udyam Extension] Error initializing settings:', err);
  }
});

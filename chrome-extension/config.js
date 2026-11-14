/**
 * Configuration for Udyam AI Assistant Chrome Extension
 */
export const DEFAULT_CONFIG = {
  // Local development URL matching the Vite frontend dev server
  localUrl: "http://localhost:5173",

  // Production URL (configurable when deployed)
  productionUrl: "https://udyam-ai-assistant.example.com",

  // FastAPI backend endpoint
  backendUrl: "http://localhost:8000",

  // Current active environment: 'local' | 'production' | 'custom'
  environment: "local",

  // Custom user-defined URL
  customUrl: ""
};

/**
 * Retrieve the active target application URL
 * Checks chrome.storage.sync first, falls back to DEFAULT_CONFIG
 */
export async function getActiveUrl() {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) {
      const data = await chrome.storage.sync.get(['environment', 'localUrl', 'productionUrl', 'customUrl']);
      const env = data.environment || DEFAULT_CONFIG.environment;

      if (env === 'production') {
        return data.productionUrl || DEFAULT_CONFIG.productionUrl;
      }
      if (env === 'custom' && data.customUrl) {
        return data.customUrl;
      }
      return data.localUrl || DEFAULT_CONFIG.localUrl;
    }
  } catch (err) {
    console.warn('Unable to access chrome.storage.sync, using default config:', err);
  }
  return DEFAULT_CONFIG.localUrl;
}

/**
 * Retrieve backend API URL
 */
export async function getBackendUrl() {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) {
      const data = await chrome.storage.sync.get(['backendUrl']);
      if (data.backendUrl) return data.backendUrl;
    }
  } catch (err) {
    console.warn('Unable to access chrome.storage.sync for backendUrl:', err);
  }
  return DEFAULT_CONFIG.backendUrl;
}

import { DEFAULT_CONFIG } from './config.js';

document.addEventListener('DOMContentLoaded', async () => {
  const form = document.getElementById('settingsForm');
  const envLocal = document.getElementById('envLocal');
  const envProduction = document.getElementById('envProduction');
  const localUrlInput = document.getElementById('localUrl');
  const productionUrlInput = document.getElementById('productionUrl');
  const backendUrlInput = document.getElementById('backendUrl');
  const resetBtn = document.getElementById('resetBtn');
  const statusMessage = document.getElementById('statusMessage');

  // Load current saved settings
  try {
    const data = await chrome.storage.sync.get(['environment', 'localUrl', 'productionUrl', 'backendUrl']);
    const env = data.environment || DEFAULT_CONFIG.environment;
    const localUrl = data.localUrl || DEFAULT_CONFIG.localUrl;
    const productionUrl = data.productionUrl || DEFAULT_CONFIG.productionUrl;
    const backendUrl = data.backendUrl || DEFAULT_CONFIG.backendUrl;

    if (env === 'production') {
      envProduction.checked = true;
    } else {
      envLocal.checked = true;
    }

    localUrlInput.value = localUrl;
    productionUrlInput.value = productionUrl;
    if (backendUrlInput) backendUrlInput.value = backendUrl;
  } catch (err) {
    console.error('Failed to load settings:', err);
  }

  // Save settings
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const selectedEnv = envProduction.checked ? 'production' : 'local';
    const localUrl = localUrlInput.value.trim() || DEFAULT_CONFIG.localUrl;
    const productionUrl = productionUrlInput.value.trim() || DEFAULT_CONFIG.productionUrl;
    const backendUrl = backendUrlInput ? (backendUrlInput.value.trim() || DEFAULT_CONFIG.backendUrl) : DEFAULT_CONFIG.backendUrl;

    try {
      await chrome.storage.sync.set({
        environment: selectedEnv,
        localUrl,
        productionUrl,
        backendUrl
      });

      statusMessage.textContent = '✓ Settings successfully saved!';
      statusMessage.style.color = '#10b981';

      setTimeout(() => {
        statusMessage.textContent = '';
      }, 3000);
    } catch (err) {
      statusMessage.textContent = `❌ Error saving settings: ${err.message}`;
      statusMessage.style.color = '#ef4444';
    }
  });

  // Reset defaults
  resetBtn.addEventListener('click', async () => {
    envLocal.checked = true;
    localUrlInput.value = DEFAULT_CONFIG.localUrl;
    productionUrlInput.value = DEFAULT_CONFIG.productionUrl;
    if (backendUrlInput) backendUrlInput.value = DEFAULT_CONFIG.backendUrl;

    try {
      await chrome.storage.sync.set({
        environment: DEFAULT_CONFIG.environment,
        localUrl: DEFAULT_CONFIG.localUrl,
        productionUrl: DEFAULT_CONFIG.productionUrl,
        backendUrl: DEFAULT_CONFIG.backendUrl
      });

      statusMessage.textContent = '✓ Reset to default settings.';
      statusMessage.style.color = '#10b981';

      setTimeout(() => {
        statusMessage.textContent = '';
      }, 3000);
    } catch (err) {
      console.error('Error resetting settings:', err);
    }
  });
});


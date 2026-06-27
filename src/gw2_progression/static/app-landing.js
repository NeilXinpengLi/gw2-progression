// ── Landing Page ──

import { createSession, clearSession } from './session-manager.js';

document.addEventListener('DOMContentLoaded', () => {
  const analyze = (inputId) => {
    const key = document.getElementById(inputId)?.value?.trim();
    if (!key) return;
    analyzeWithKey(key);
  };

  document.getElementById('landing-analyze-btn')?.addEventListener('click', () => analyze('landing-key-input'));
  document.getElementById('landing-key-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') analyze('landing-key-input'); });
  document.getElementById('cta-analyze-btn')?.addEventListener('click', () => analyze('cta-key-input'));
  document.getElementById('cta-key-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') analyze('cta-key-input'); });

  document.getElementById('landing-demo-btn')?.addEventListener('click', goToDemo);
  document.getElementById('cta-demo-btn')?.addEventListener('click', goToDemo);
});

async function analyzeWithKey(apiKey) {
  clearSession();
  const token = await createSession(apiKey);
  if (token) {
    window.location.href = '/account';
  } else {
    window.location.href = '/account?api_key=' + encodeURIComponent(apiKey);
  }
}

function goToDemo() {
  window.location.href = '/account';
}

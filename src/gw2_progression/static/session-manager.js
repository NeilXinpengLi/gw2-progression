// ── Session Manager ──
// Unified session handling for all pages.
// Versioned storage key ensures code updates invalidate old sessions.

const STORAGE_KEY = 'gw2_session_v2';
let _sessionToken = null;

export function getToken() {
  return _sessionToken;
}

export function isLoggedIn() {
  return _sessionToken !== null && _sessionToken.length > 0;
}

export async function initSession() {
  // 1. Try restoring from localStorage
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && saved.length > 40) {
      _sessionToken = saved;
      // 2. Validate the saved session
      const valid = await validateSession(saved);
      if (valid) {
        return _sessionToken;
      }
      // Invalid → clear
      clearSession();
    }
  } catch(e) {
    clearSession();
  }
  return null;
}

export async function createSession(apiKey) {
  try {
    const res = await fetch('/auth/session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({api_key: apiKey}),
    });
    if (!res.ok) return null;
    const data = await res.json();
    _sessionToken = data.token;
    try { localStorage.setItem(STORAGE_KEY, _sessionToken); } catch(e) {}
    return _sessionToken;
  } catch(e) {
    return null;
  }
}

export function clearSession() {
  _sessionToken = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
    // Also remove old key for backward compat
    localStorage.removeItem('gw2_session');
  } catch(e) {}
}

export function getEffectiveKey(rawInput) {
  // If we have a valid session token, use it.
  // If the user entered a key that looks like an API key (not a token),
  // and it differs from our cached token, create a new session.
  if (_sessionToken) {
    // User entered something different → create new session
    if (rawInput && rawInput !== _sessionToken && rawInput.length > 40) {
      return null; // signal: need new session
    }
    return _sessionToken;
  }
  return rawInput;
}

async function validateSession(token) {
  try {
    const res = await fetch('/auth/session/validate?token=' + encodeURIComponent(token));
    return res.ok;
  } catch(e) {
    return false;
  }
}

// ── Insight Page — AI Overlay Layer ──

import { fmtCoin, fmtCoinShort } from './app-shared.js';

let _sessionToken = null;

document.addEventListener('DOMContentLoaded', () => {
  // OS nav
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    if (page === 'account') window.location.href = '/account';
    else if (page === 'plan') window.location.href = '/plan';
  });

  // Load insight data
  try {
    const saved = localStorage.getItem('gw2_session');
    if (saved) {
      _sessionToken = saved;
      loadInsight(saved);
    }
  } catch(e) {}
});

async function loadInsight(token) {
  try {
    const res = await fetch(`/api/v1/decide?api_key=${encodeURIComponent(token)}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({api_key: token}) });
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('insight-account-badge').classList.remove('hidden');
    document.getElementById('insight-account-name').textContent = data.account_name || '—';

    // Hidden Wealth — from overview
    const overviewRes = await fetch(`/api/account/overview?api_key=${encodeURIComponent(token)}`);
    if (overviewRes.ok) {
      const ov = await overviewRes.json();
      const hw = ov.kpis?.hidden_wealth || 0;
      document.getElementById('insight-hidden-wealth').textContent = fmtCoin(hw);
    }

    // Build readiness
    const p0 = data.p0 || [];
    const p1 = data.p1 || [];
    const p2 = data.p2 || [];
    const total = p0.length + p1.length + p2.length;
    document.getElementById('insight-build-ready').textContent = `${total} actions available`;

    // Legendary
    document.getElementById('insight-legendary').textContent = '—';

    // Recommendations
    const container = document.getElementById('insight-recommendations');
    const allActions = [...p0, ...p1, ...p2].slice(0, 5);
    if (allActions.length === 0) {
      container.innerHTML = '<div class="dim" style="text-align:center;padding:20px">No recommendations yet.</div>';
      return;
    }
    container.innerHTML = allActions.map(a => `
      <div style="display:flex;align-items:center;gap:10px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:6px">
        <span style="font-size:16px">${a.icon || '•'}</span>
        <span style="flex:1;font-size:13px"><strong>${escHtml(a.action || '')}</strong>: ${escHtml(a.reason || '')}</span>
        <span style="font-size:12px;color:var(--gold-light);font-weight:600">${a.reward_copper ? fmtCoinShort(a.reward_copper) : ''}</span>
      </div>`).join('');
  } catch(e) {
    console.warn('Insight load error:', e);
  }
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[m] || m);
}

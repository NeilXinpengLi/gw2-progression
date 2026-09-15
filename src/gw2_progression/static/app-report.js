// ── Report Page — Monetization Layer ──
import { initSession } from './session-manager.js';
import { fmtCoin } from './app-shared.js';

document.addEventListener('DOMContentLoaded', async () => {
  // Nav
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  const token = await initSession();
  if (token) loadReport(token);
});

async function loadReport(token) {
  try {
    const r = await fetch(`/api/account/overview?api_key=${encodeURIComponent(token)}`);
    if (!r.ok) return;
    const d = await r.json();

    document.getElementById('report-account-name').textContent = d.account?.name || '—';
    document.getElementById('report-total-value').textContent = fmtCoin(d.kpis?.account_value || 0);
    document.getElementById('report-char-count').textContent = `${d.kpis?.character_count || 0} characters`;
    document.getElementById('report-build-ready').textContent = `${d.kpis?.build_ready_count ?? '—'} ready`;
  } catch(e) {
    console.warn('Report load error:', e);
  }
}

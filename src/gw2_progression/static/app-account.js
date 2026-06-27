// ── Account Overview Dashboard ──

import {
  _itemCache, _currencyCache, _matCatCache, _masteryCache, _mapCache,
  _skinCache, _colorCache, _guildCache,
  backendResolve, backendResolveSingle, cappedCacheAdd,
  resolveItems, resolveCurrencies, resolveMatCategories, resolveMasteries,
  resolveMaps, resolveSkins, resolveGuilds, resolveColors, resolveSearch,
  rgbToHex, itemName, itemIcon, currencyName, matCatName, masteryName,
  masteryRegion, mapName, skinName, skinIcon, colorHex, fmtCoin, fmtCoinShort,
} from './app-shared.js';

let _sessionToken = null;
let _abortController = null;
let _accountData = null;
let _overviewData = null;
let _trendChart = null;

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('analyze-btn').addEventListener('click', runAnalyze);
  document.getElementById('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') runAnalyze(); });
  document.getElementById('btn-refresh')?.addEventListener('click', runAnalyze);

  // OS nav switching
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    document.querySelectorAll('#os-nav button').forEach(b => {
      b.classList.remove('active');
      b.style.color = 'var(--text-dim)';
      b.style.borderTop = 'none';
    });
    document.querySelectorAll('.page-section').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    btn.style.color = 'var(--gold)';
    btn.style.borderTop = '2px solid var(--gold)';
    const page = document.getElementById('page-' + btn.dataset.nav);
    if (page) page.classList.add('active');
  });

  // Restore session
  try {
    const saved = localStorage.getItem('gw2_session');
    if (saved) {
      _sessionToken = saved;
      document.getElementById('key-input').value = saved;
      setTimeout(runAnalyze, 300);
    }
  } catch(e) {}
});

// ── Analyze ──

async function runAnalyze() {
  const rawKey = document.getElementById('key-input').value.trim();
  if (!rawKey) return showError('Please paste a GW2 API key first.');

  if (_abortController) _abortController.abort();
  _abortController = new AbortController();
  const signal = _abortController.signal;

  showLoading(true);
  hideAllSections();

  let useKey = rawKey;

  // If user entered a new key (different from cached token), force re-auth
  if (_sessionToken && rawKey !== _sessionToken && rawKey.length > 40) {
    _sessionToken = null;
    localStorage.removeItem('gw2_session');
  }

  // Create session if needed
  if (!_sessionToken) {
    try {
      const sessionRes = await fetch('/auth/session', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: rawKey}), signal,
      });
      if (sessionRes.ok) {
        const session = await sessionRes.json();
        _sessionToken = session.token;
        useKey = session.token;
        localStorage.setItem('gw2_session', _sessionToken);
      }
    } catch(e) { /* use raw key */ }
  } else {
    useKey = _sessionToken;
  }

  // Fetch overview data
  try {
    const [overviewRes, analyzeRes] = await Promise.all([
      fetch(`/api/account/overview?api_key=${encodeURIComponent(useKey)}`, { signal }),
      fetch('/analyze', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: useKey}), signal,
      }),
    ]);

    if (!overviewRes.ok) {
      const err = await overviewRes.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${overviewRes.status}`);
    }

    _overviewData = await overviewRes.json();
    _accountData = analyzeRes.ok ? await analyzeRes.json() : null;

    showLoading(false);
    renderDashboard(_overviewData);
    loadChart();

    if (_accountData) {
      // Resolve item names for assets
      const ids = [];
      for (const row of _overviewData.assets || []) {
        // No item IDs in overview yet
      }
      renderInsightPreview();
    }

    showStatusBadge('active');
  } catch (e) {
    if (e.name === 'AbortError') return;
    showLoading(false);
    showError(e.message);
    showStatusBadge('error');
  }
}

// ── Render Dashboard ──

function renderDashboard(data) {
  hideAllSections();

  // Header
  document.getElementById('header-account-name').textContent = data.account?.name || '—';
  document.getElementById('header-last-sync').textContent = `Last sync: ${data.snapshot_time || 'just now'}`;

  // KPI Row
  const kpis = data.kpis || {};
  setKpi('account-value', fmtCoin(kpis.account_value || 0));
  setKpi('liquid-sell', fmtCoin(kpis.liquid_sell || 0));
  setKpi('liquid-buy', fmtCoin(kpis.liquid_buy || 0));
  setKpi('hidden-wealth', fmtCoin(kpis.hidden_wealth || 0));
  setKpi('legendary', `${kpis.legendary_goals ?? '—'} goals`);
  setKpi('build-ready', `${kpis.build_ready_count ?? '—'} / ${kpis.character_count || 0}`);

  // Asset Table
  const tbody = document.getElementById('asset-tbody');
  tbody.innerHTML = '';
  let total = 0;
  for (const row of data.assets || []) {
    total += row.total_value || 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.category}</td>
      <td class="num">${fmtCoin(row.total_value || 0)}</td>
      <td class="num">${fmtCoin(row.liquid_sell || 0)}</td>
      <td class="num">${fmtCoin(row.liquid_buy || 0)}</td>
      <td class="num">${row.percentage ?? 0}%</td>
      <td><span class="risk-dot" data-risk="${row.risk_flag || 'none'}">● ${row.risk_flag || 'none'}</span></td>`;
    tbody.appendChild(tr);
  }
  document.getElementById('asset-total').textContent = `${fmtCoin(total)} total`;

  // Character Table
  const charTbody = document.getElementById('char-tbody');
  charTbody.innerHTML = '';
  for (const ch of data.characters || []) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escHtml(ch.name)}</strong></td>
      <td>${escHtml(ch.profession || '—')}</td>
      <td class="num">${ch.level ?? '—'}</td>
      <td class="num">${ch.playtime || '—'}</td>
      <td class="num">${ch.gear_value ? fmtCoin(ch.gear_value) : '—'}</td>
      <td>${ch.build_status || '—'}</td>
      <td>${ch.last_login || '—'}</td>`;
    charTbody.appendChild(tr);
  }

  // Show sections
  document.getElementById('account-header').classList.remove('hidden');
  document.getElementById('kpi-section').classList.remove('hidden');
  document.getElementById('asset-section').classList.remove('hidden');
  document.getElementById('character-section').classList.remove('hidden');
  document.getElementById('status-panel').classList.remove('hidden');

  // Status panel
  document.getElementById('status-api').textContent = 'active';
  document.getElementById('status-freshness').textContent = 'fresh';
  document.getElementById('status-permissions').textContent = `${data.characters?.length || 0} characters · ${data.assets?.length || 0} asset categories`;
}

// ── Chart ──

function loadChart() {
  const canvas = document.getElementById('trend-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  if (_trendChart) { _trendChart.destroy(); _trendChart = null; }

  // Generate mock 30-day trend from available data
  const labels = [];
  const values = [];
  const baseValue = (_overviewData?.kpis?.account_value || 0) / 10000;
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    labels.push(d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'}));
    // Smooth random walk from base
    const noise = (Math.random() - 0.5) * baseValue * 0.3;
    values.push(Math.max(0, baseValue + noise * (i / 30)));
  }

  _trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Account Value (g)',
        data: values,
        borderColor: '#c8956c',
        backgroundColor: 'rgba(200, 149, 108, 0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 1,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#888', maxTicksLimit: 10, font: {size: 10} }, grid: { display: false } },
        y: { ticks: { color: '#888', font: {size: 10} }, grid: { color: '#222' } },
      },
    },
  });

  document.getElementById('chart-section').classList.remove('hidden');
}

// ── Insight Preview ──

function renderInsightPreview() {
  const container = document.getElementById('insight-actions');
  container.innerHTML = '';

  const actions = [
    { action: 'Review High-Value Items', reward: '+', reason: 'Top items drive account value' },
    { action: 'Check Trading Post', reward: '+', reason: 'Active orders may have profit opportunities' },
  ];

  for (const a of actions) {
    const div = document.createElement('div');
    div.className = 'insight-action';
    div.innerHTML = `
      <span style="font-size:13px;font-weight:600;color:var(--gold-light)">${a.action}</span>
      <span class="reason">${a.reason}</span>
    `;
    container.appendChild(div);
  }

  document.getElementById('insight-preview').classList.remove('hidden');
}

// ── Helpers ──

function setKpi(id, value) {
  const el = document.getElementById(`kpi-${id}`);
  if (el) el.textContent = value;
}

function showLoading(show) {
  document.getElementById('loading-state').classList.toggle('hidden', !show);
}

function showError(msg) {
  document.getElementById('error-message').textContent = msg;
  document.getElementById('error-state').classList.remove('hidden');
}

function showStatusBadge(status) {
  const badge = document.getElementById('api-status-badge');
  if (!badge) return;
  badge.dataset.status = status;
  const labels = {active: '● Active', stale: '● Stale', error: '● Error'};
  badge.textContent = labels[status] || '● Unknown';
}

function hideAllSections() {
  ['account-header', 'kpi-section', 'chart-section', 'asset-section',
   'character-section', 'guild-section', 'insight-preview', 'status-panel',
   'loading-state', 'error-state'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
  });
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>"]/g, function(m) {
    if (m === '&') return '&amp;'; if (m === '<') return '&lt;';
    if (m === '>') return '&gt;'; if (m === '"') return '&quot;';
    return m;
  });
}

window.switchPage = function(page) {
  const btn = document.querySelector(`#os-nav button[data-nav="${page}"]`);
  if (btn) btn.click();
};

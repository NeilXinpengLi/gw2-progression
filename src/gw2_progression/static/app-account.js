// ── Account Overview — Layered Cognitive UI ──

import { fmtCoin, fmtCoinShort, loadIconSprite } from './app-shared.js';
import { initSession, createSession, clearSession, getToken, getEffectiveKey } from './session-manager.js';

let _abortController = null;
let _overviewData = null;

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('analyze-btn').addEventListener('click', runAnalyze);
  document.getElementById('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') runAnalyze(); });
  document.getElementById('btn-refresh')?.addEventListener('click', runAnalyze);
  document.getElementById('btn-export')?.addEventListener('click', exportData);

  // Nav
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  // Tab switching
  document.querySelector('.layer-tab-bar')?.addEventListener('click', e => {
    const btn = e.target.closest('.layer-tab');
    if (!btn) return;
    document.querySelectorAll('.layer-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.layer-tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    const tab = document.getElementById('tab-' + btn.dataset.tab);
    if (tab) tab.classList.add('active');
  });

  const token = await initSession();
  if (token) {
    document.getElementById('key-input').value = token;
    runAnalyze();
  }
});

async function runAnalyze() {
  const rawKey = document.getElementById('key-input').value.trim();
  if (!rawKey) return showError('Please paste a GW2 API key first.');
  if (_abortController) _abortController.abort();
  _abortController = new AbortController();
  showLoading(true);

  let useKey = getEffectiveKey(rawKey);
  if (useKey === null || !getToken()) {
    const newToken = await createSession(rawKey);
    if (newToken) useKey = newToken;
    else useKey = rawKey;
  }

  try {
    const r = await fetch(`/api/account/overview?api_key=${encodeURIComponent(useKey)}`, { signal: _abortController.signal });
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
    _overviewData = await r.json();
    showLoading(false);
    renderOverview(_overviewData);
    showStatusBadge('active');
  } catch (e) {
    if (e.name === 'AbortError') return;
    showLoading(false);
    showError(e.message);
    showStatusBadge('error');
  }
}

function renderOverview(data) {
  document.getElementById('key-section').style.display = 'none';
  document.getElementById('layer-overview').classList.remove('hidden');
  document.getElementById('layer-tabs').classList.remove('hidden');
  document.getElementById('layer-ai').classList.remove('hidden');

  const a = data.account || {};
  const k = data.kpis || {};
  document.getElementById('header-account-name').textContent = a.name || '—';
  document.getElementById('header-last-sync').textContent = `Last sync: ${data.snapshot_time || 'just now'}`;

  // Overview KPIs
  document.getElementById('ov-total-value').textContent = fmtCoin(k.account_value || 0);
  document.getElementById('ov-liquid-value').textContent = fmtCoin(k.liquid_sell_after_fee || 0);
  document.getElementById('ov-hidden-wealth').textContent = fmtCoin(k.hidden_wealth || 0);

  // Progress bar
  const og = data.object_graph || {};
  const prog = og.progression || {};
  document.getElementById('overview-progress').innerHTML = `
    <div class="ov-stat"><span class="ov-stat-lbl">Skins</span><span class="ov-stat-val">${k.skin_count || 0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">Masteries</span><span class="ov-stat-val">${k.mastery_count || 0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">Fractal</span><span class="ov-stat-val">${k.fractal_level || 0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">WvW Rank</span><span class="ov-stat-val">${k.wvw_rank || 0}</span></div>
  `;

  // Economy tab
  renderEconomy(data.assets || []);

  // Progress tab
  renderProgression(data);

  // Collection tab
  renderCollection(data);

  // Characters tab
  renderCharacters(data.characters || []);

  // AI Drawer
  renderAIDrawer(k);
}

function renderEconomy(assets) {
  const list = document.getElementById('economy-list');
  list.innerHTML = assets.map(a => `
    <div class="econ-row">
      <div class="econ-info">
        <span class="econ-cat">${a.category}</span>
        <span class="econ-pct">${a.percentage}%</span>
      </div>
      <div class="econ-vals">
        <span class="econ-val">${fmtCoin(a.total_value || 0)}</span>
        <span class="econ-sub">${a.risk_flag}</span>
      </div>
    </div>`).join('');
}

function renderProgression(data) {
  const k = data.kpis || {};
  const ad = data.additional_data || {};
  const grid = document.getElementById('progression-grid');
  grid.innerHTML = `
    <div class="prog-card"><div class="prog-cat">Combat</div>
      <div class="prog-rows">
        <div class="prog-row"><span>Fractal Level</span><span class="prog-val">${k.fractal_level || 0}</span></div>
        <div class="prog-row"><span>WvW Rank</span><span class="prog-val">${k.wvw_rank || 0}</span></div>
        <div class="prog-row"><span>PvP Rank</span><span class="prog-val">${ad.pvp_rank || 0}</span></div>
      </div>
    </div>
    <div class="prog-card"><div class="prog-cat">Mastery</div>
      <div class="prog-rows">
        <div class="prog-row"><span>AP (Daily)</span><span class="prog-val">${k.daily_ap || 0}</span></div>
        <div class="prog-row"><span>AP (Monthly)</span><span class="prog-val">${k.monthly_ap || 0}</span></div>
        <div class="prog-row"><span>Masteries</span><span class="prog-val">${k.mastery_count || 0}</span></div>
        <div class="prog-row"><span>Build Templates</span><span class="prog-val">${ad.build_storage_count || 0}</span></div>
      </div>
    </div>
    <div class="prog-card"><div class="prog-cat">Social</div>
      <div class="prog-rows">
        <div class="prog-row"><span>Characters</span><span class="prog-val">${k.character_count || 0}</span></div>
        <div class="prog-row"><span>Guilds</span><span class="prog-val">${ad.guild_count || 0}</span></div>
        <div class="prog-row"><span>Achievements</span><span class="prog-val">${k.achievement_count || 0}</span></div>
      </div>
    </div>`;
}

function renderCollection(data) {
  const k = data.kpis || {};
  const ad = data.additional_data || {};
  const grid = document.getElementById('collection-grid');
  grid.innerHTML = `
    <div class="coll-card"><span class="coll-icon">🎨</span><span class="coll-label">Skins</span><span class="coll-count">${k.skin_count || 0}</span></div>
    <div class="coll-card"><span class="coll-icon">🎨</span><span class="coll-label">Dyes</span><span class="coll-count">${ad.unlocked_dyes || 0}</span></div>
    <div class="coll-card"><span class="coll-icon">🧸</span><span class="coll-label">Minis</span><span class="coll-count">${ad.unlocked_minis || 0}</span></div>
    <div class="coll-card"><span class="coll-icon">⭐</span><span class="coll-label">Finishers</span><span class="coll-count">${ad.finisher_count || data.object_graph?.unlock_counts?.finishers || 0}</span></div>`;
}

function renderCharacters(chars) {
  const container = document.getElementById('char-cards');
  if (!chars || chars.length === 0) {
    container.innerHTML = '<div class="dim">No characters found.</div>';
    return;
  }
  container.innerHTML = chars.map(c => {
    const profColors = { Guardian: '#6b8', Necromancer: '#86a', Elementalist: '#c84', Mesmer: '#a6c', Warrior: '#c86', Revenant: '#a60', Ranger: '#8a6', Thief: '#888', Engineer: '#a86' };
    const color = profColors[c.profession] || '#888';
    return `<div class="char-card" style="border-left:3px solid ${color}">
      <div class="char-top">
        <span class="char-name">${escHtml(c.name)}</span>
        <span class="char-prof">${c.profession}</span>
        <span class="char-lv">Lv${c.level}</span>
      </div>
      <div class="char-meta">
        <span>${c.playtime || '—'}</span>
        <span>${c.gear_value ? fmtCoin(c.gear_value) : '—'}</span>
        <span>${c.build_status || '—'}</span>
      </div>
      <div class="char-login">${c.last_login || '—'}</div>
    </div>`;
  }).join('');
}

function renderAIDrawer(k) {
  const content = document.getElementById('ai-drawer-content');
  if (!content) return;
  content.innerHTML = `
    <div class="ai-item"><span>Hidden Wealth</span><span class="ai-val">${fmtCoin(k.hidden_wealth || 0)}</span></div>
    <div class="ai-item"><span>Build Ready</span><span class="ai-val">${k.build_ready_count ?? '—'} / ${k.character_count || 0}</span></div>
    <div class="ai-item"><span>Liquid Value</span><span class="ai-val">${fmtCoin(k.liquid_sell_after_fee || 0)}</span></div>`;
}

function showLoading(v) {
  document.getElementById('key-section').style.display = v ? 'none' : '';
  document.getElementById('loading-state').classList.toggle('hidden', !v);
  document.getElementById('error-state').classList.add('hidden');
}

function showError(msg) {
  document.getElementById('error-message').textContent = msg;
  document.getElementById('error-state').classList.remove('hidden');
}

function showStatusBadge(status) {
  const badge = document.getElementById('api-status-badge');
  if (!badge) return;
  badge.dataset.status = status;
  badge.textContent = { active: '● Active', stale: '● Stale', error: '● Error' }[status] || '● Unknown';
}

function exportData() {
  if (!_overviewData) return;
  const data = { exported_at: new Date().toISOString(), account: _overviewData.account, kpis: _overviewData.kpis, assets: _overviewData.assets, characters: _overviewData.characters };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gw2-account-${data.account?.name || 'unknown'}-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function escHtml(s) { if (!s) return ''; return String(s).replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[m] || m); }

import { fmtCoin, fmtCoinShort, loadIconSprite } from './app-shared.js';
import { initSession, createSession, clearSession, getToken, getEffectiveKey } from './session-manager.js';

let _abortController = null;
let _overviewData = null;

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('analyze-btn').addEventListener('click', runAnalyze);
  document.getElementById('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') runAnalyze(); });
  document.getElementById('btn-refresh')?.addEventListener('click', runAnalyze);
  document.getElementById('btn-export')?.addEventListener('click', exportData);

  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  document.querySelector('.layer-tab-bar')?.addEventListener('click', e => {
    const btn = e.target.closest('.layer-tab');
    if (!btn) return;
    switchTab(btn.dataset.tab);
  });

  const token = await initSession();
  if (token) {
    document.getElementById('key-input').value = token;
    runAnalyze();
  }
});

function switchTab(tabId) {
  document.querySelectorAll('.layer-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.layer-tab-content').forEach(t => t.classList.remove('active'));
  const tabBtn = document.querySelector(`.layer-tab[data-tab="${tabId}"]`);
  if (tabBtn) tabBtn.classList.add('active');
  const tab = document.getElementById('tab-' + tabId);
  if (tab) tab.classList.add('active');
  selectTreeNode(tabId);
}

function selectTreeNode(id) {
  document.querySelectorAll('.tn-item').forEach(n => n.classList.remove('selected'));
  const node = document.getElementById('tn-' + id);
  if (node) node.classList.add('selected');
}

function scrollToChar(charName) {
  const card = document.getElementById('char-' + charName.replace(/\s+/g, '-').toLowerCase());
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

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

  const encKey = encodeURIComponent(useKey);
  const signal = _abortController.signal;
  const refresh = Date.now(); // bust cache on manual refresh

  try {
    // ── PHASE 1: lite — get account name + KPIs, render overview immediately ──
    const r1 = await fetch(`/api/account/overview?api_key=${encKey}&lite=true&refresh=${refresh}`, { signal });
    if (!r1.ok) { const e = await r1.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r1.status}`); }
    const lite = await r1.json();
    showLoading(false);
    renderLite(lite);
    showStatusBadge('active');

    // ── PHASE 2: full — get assets, characters, progression, collection ──
    const r2 = await fetch(`/api/account/overview?api_key=${encKey}&refresh=${refresh}`, { signal });
    if (!r2.ok) { const e = await r2.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r2.status}`); }
    _overviewData = await r2.json();
    renderFull(_overviewData);
  } catch (e) {
    if (e.name === 'AbortError') return;
    showLoading(false);
    showError(e.message);
    showStatusBadge('error');
  }
}

function renderLite(data) {
  document.getElementById('key-section').style.display = 'none';
  document.getElementById('layer-overview').classList.remove('hidden');
  document.getElementById('layer-content').classList.remove('hidden');
  document.getElementById('layer-ai').classList.remove('hidden');

  const a = data.account || {};
  const k = data.kpis || {};
  document.getElementById('header-account-name').textContent = a.name || '—';
  document.getElementById('header-last-sync').textContent = `Loading full data…`;
  document.getElementById('ov-total-value').textContent = '…';
  document.getElementById('ov-liquid-value').textContent = '…';
  document.getElementById('ov-hidden-wealth').textContent = '…';
  document.getElementById('overview-progress').innerHTML = `
    <div class="ov-stat"><span class="ov-stat-lbl">Skins</span><span class="ov-stat-val">${k.skin_count || 0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">Masteries</span><span class="ov-stat-val">${k.mastery_count || 0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">Fractal</span><span class="ov-stat-val">${k.fractal_level || 0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">WvW Rank</span><span class="ov-stat-val">${k.wvw_rank || 0}</span></div>`;

  document.querySelectorAll('.tab-skeleton').forEach(el => el.remove());
  document.querySelectorAll('.layer-tab-content').forEach(t => {
    const sk = document.createElement('div');
    sk.className = 'tab-skeleton';
    sk.innerHTML = '<div class="sk-shimmer"><div class="sk-block" style="height:80px"></div><div class="sk-block" style="height:120px;margin-top:8px"></div><div class="sk-block" style="height:60px;margin-top:8px"></div></div>';
    t.appendChild(sk);
  });
}

function renderFull(data) {
  const k = data.kpis || {};
  document.getElementById('header-last-sync').textContent = `Last sync: ${data.snapshot_time || 'just now'}`;
  document.getElementById('ov-total-value').textContent = fmtCoin(k.account_value || 0);
  document.getElementById('ov-liquid-value').textContent = fmtCoin(k.liquid_sell_after_fee || 0);
  document.getElementById('ov-hidden-wealth').textContent = fmtCoin(k.hidden_wealth || 0);

  document.querySelectorAll('.tab-skeleton').forEach(el => el.remove());

  renderExplorerTree(data);
  renderEconomy(data.assets || []);
  renderProgression(data);
  renderCollection(data);
  renderCharacters(data.characters || []);
  renderAIDrawer(k);
}

function renderExplorerTree(data) {
  const tree = document.getElementById('explorer-tree');
  if (!tree) return;
  const chars = (data.characters || []).map(c => `<div class="tn-item tn-child" data-tab="characters" data-char="${escHtml(c.name)}" id="tn-char-${escHtml(c.name).replace(/\s+/g, '-').toLowerCase()}"><span class="tn-icon">⛨</span>${escHtml(c.name)}</div>`).join('');
  tree.innerHTML = `
    <div class="tn-section">OBJECT GRAPH</div>
    <div class="tn-item tn-root selected" data-tab="economy" id="tn-economy"><svg class="tn-svg" width="16" height="16"><use href="#sym-tree-economy"/></svg>Economy</div>
    <div class="tn-item tn-root" data-tab="progress" id="tn-progress"><svg class="tn-svg" width="16" height="16"><use href="#sym-tree-progress"/></svg>Progression</div>
    <div class="tn-item tn-root" data-tab="collection" id="tn-collection"><svg class="tn-svg" width="16" height="16"><use href="#sym-tree-collection"/></svg>Collections</div>
    <div class="tn-item tn-root tn-parent" data-tab="characters" id="tn-characters"><svg class="tn-svg" width="16" height="16"><use href="#sym-tree-characters"/></svg>Characters</div>
    ${chars}
  `;
  tree.querySelectorAll('.tn-item').forEach(el => {
    el.addEventListener('click', () => {
      const tab = el.dataset.tab;
      const charName = el.dataset.char;
      tree.querySelectorAll('.tn-item').forEach(n => n.classList.remove('selected'));
      el.classList.add('selected');
      switchTab(tab);
      if (charName) scrollToChar(charName);
    });
  });
}

function renderEconomy(assets) {
  const list = document.getElementById('economy-list');
  const expandedRows = {
    'Wallet': true,
    'Bank': true,
    'Materials': true,
    'Shared Inventory': false,
    'Trading Post': false
  };
  list.innerHTML = assets.map(a => `
    <div class="econ-row ${expandedRows[a.category] ? 'expanded' : ''}" data-cat="${a.category}">
      <div class="econ-header" onclick="this.closest('.econ-row').classList.toggle('expanded')">
        <div class="econ-info">
          <span class="econ-toggle">▶</span>
          <span class="econ-cat">${a.category}</span>
          <span class="econ-pct">${a.percentage}%</span>
        </div>
        <div class="econ-vals">
          <span class="econ-val">${fmtCoin(a.total_value || 0)}</span>
          <span class="econ-sub">${a.risk_flag}</span>
        </div>
      </div>
      <div class="econ-detail">
        <div class="econ-detail-row"><span>Items</span><span>${a.count || 0}</span></div>
        <div class="econ-detail-row"><span>Distinct</span><span>${a.distinct_count || a.count || 0}</span></div>
        <div class="econ-detail-row"><span>Avg Value</span><span>${a.count ? fmtCoin(Math.round(a.total_value / a.count)) : '—'}</span></div>
      </div>
    </div>`).join('');
}

function renderProgression(data) {
  const k = data.kpis || {};
  const ad = data.additional_data || {};
  const grid = document.getElementById('progression-grid');
  grid.innerHTML = `
    <div class="prog-card"><div class="prog-cat">Combat</div>
      <div class="prog-timeline">
        <div class="prog-milestone"><span class="pm-label">Fractal Level</span><span class="pm-stat">${k.fractal_level || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.fractal_level||0)/150)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">WvW Rank</span><span class="pm-stat">${k.wvw_rank || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.wvw_rank||0)/300)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">PvP Rank</span><span class="pm-stat">${ad.pvp_rank || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((ad.pvp_rank||0)/100)*100)}%"></div></div></div>
      </div>
    </div>
    <div class="prog-card"><div class="prog-cat">Mastery</div>
      <div class="prog-timeline">
        <div class="prog-milestone"><span class="pm-label">AP (Daily)</span><span class="pm-stat">${k.daily_ap || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.daily_ap||0)/10000)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">AP (Monthly)</span><span class="pm-stat">${k.monthly_ap || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.monthly_ap||0)/5000)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">Masteries</span><span class="pm-stat">${k.mastery_count || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.mastery_count||0)/90)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">Builds</span><span class="pm-stat">${ad.build_storage_count || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((ad.build_storage_count||0)/30)*100)}%"></div></div></div>
      </div>
    </div>
    <div class="prog-card"><div class="prog-cat">Social</div>
      <div class="prog-timeline">
        <div class="prog-milestone"><span class="pm-label">Characters</span><span class="pm-stat">${k.character_count || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.character_count||0)/70)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">Guilds</span><span class="pm-stat">${ad.guild_count || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((ad.guild_count||0)/5)*100)}%"></div></div></div>
        <div class="prog-milestone"><span class="pm-label">Achievements</span><span class="pm-stat">${k.achievement_count || 0}</span><div class="pm-bar"><div class="pm-fill" style="width:${Math.min(100, ((k.achievement_count||0)/5000)*100)}%"></div></div></div>
      </div>
    </div>`;
}

function renderCollection(data) {
  const k = data.kpis || {};
  const ad = data.additional_data || {};
  const grid = document.getElementById('collection-grid');
  grid.innerHTML = `
    <div class="coll-card"><svg class="coll-svg" width="28" height="28" viewBox="0 0 24 24"><g fill="none" stroke="#c8956c" stroke-width="1.5"><circle cx="12" cy="12" r="7"/><path d="M12 7v10M7 12h10"/></g></svg><span class="coll-label">Skins</span><span class="coll-count">${k.skin_count || 0}</span></div>
    <div class="coll-card"><svg class="coll-svg" width="28" height="28" viewBox="0 0 24 24"><g fill="none" stroke="#c8956c" stroke-width="1.5"><path d="M8 8l8 8M8 16l8-8"/><circle cx="12" cy="12" r="10"/></g></svg><span class="coll-label">Dyes</span><span class="coll-count">${ad.unlocked_dyes || 0}</span></div>
    <div class="coll-card"><svg class="coll-svg" width="28" height="28" viewBox="0 0 24 24"><g fill="none" stroke="#c8956c" stroke-width="1.5"><rect x="6" y="3" width="12" height="18" rx="2"/><circle cx="12" cy="10" r="2"/><circle cx="12" cy="16" r="1.5"/></g></svg><span class="coll-label">Minis</span><span class="coll-count">${ad.unlocked_minis || 0}</span></div>
    <div class="coll-card"><svg class="coll-svg" width="28" height="28" viewBox="0 0 24 24"><g fill="none" stroke="#c8956c" stroke-width="1.5"><polygon points="12 2 15 9 22 9 16 14 18 22 12 17 6 22 8 14 2 9 9 9 12 2"/></g></svg><span class="coll-label">Finishers</span><span class="coll-count">${ad.finisher_count || data.object_graph?.unlock_counts?.finishers || 0}</span></div>`;
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
    return `<div class="char-card" id="char-${escHtml(c.name).replace(/\s+/g, '-').toLowerCase()}" style="border-left:3px solid ${color}">
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

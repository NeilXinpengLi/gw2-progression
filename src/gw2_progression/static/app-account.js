import { fmtCoin } from './app-shared.js';
import { initSession, createSession, getToken, getEffectiveKey } from './session-manager.js';

let _abortController = null;
let _overviewData = null;
let _activeTab = 'economy';
let _activeSub = null;

const CATEGORY_MAP = {
  wallet: 'wallet',
  bank: 'bank',
  materials: 'material storage',
  tradingpost: 'trading post',
  equipment: 'equipment',
  shared_inventory: 'shared inventory',
  character_inventory: 'character inventory',
};

const TREE = {
  economy: { label: 'Economy', icon: 'sym-tree-economy', sub: [
    { id: 'wallet', label: 'Wallet', icon: 'sym-sub-wallet' },
    { id: 'materials', label: 'Material Storage', icon: 'sym-asset-materials' },
    { id: 'bank', label: 'Bank', icon: 'sym-asset-bank' },
    { id: 'equipment', label: 'Equipment', icon: 'sym-asset-equipment' },
    { id: 'character_inventory', label: 'Character Inventory', icon: 'sym-sub-wallet' },
    { id: 'shared_inventory', label: 'Shared Inventory', icon: 'sym-asset-bank' },
    { id: 'tradingpost', label: 'Trading Post', icon: 'sym-sub-trading' },
  ]},
  progress: { label: 'Progression', icon: 'sym-tree-progress', sub: [
    { id: 'achievements', label: 'Achievements', icon: 'sym-sub-achievements' },
    { id: 'masteries', label: 'Masteries', icon: 'sym-sub-mastery' },
    { id: 'pvp', label: 'PvP', icon: 'sym-sub-pvp' },
    { id: 'wvw', label: 'WvW', icon: 'sym-sub-wvw' },
    { id: 'fractals', label: 'Fractals', icon: 'sym-sub-fractal' },
  ]},
  collection: { label: 'Collections', icon: 'sym-tree-collection', sub: [
    { id: 'skins', label: 'Skins', icon: 'sym-sub-skins' },
    { id: 'dyes', label: 'Dyes', icon: 'sym-sub-dyes' },
    { id: 'minis', label: 'Minis', icon: 'sym-sub-minis' },
    { id: 'finishers', label: 'Finishers', icon: 'sym-kpi-legendary' },
  ]},
  characters: { label: 'Characters', icon: 'sym-tree-characters', sub: [] },
};

document.addEventListener('DOMContentLoaded', async () => {
  // Nav — attach FIRST so it survives any error in handlers below
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  try {
    document.getElementById('analyze-btn').addEventListener('click', runAnalyze);
    document.getElementById('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') runAnalyze(); });
    document.getElementById('btn-refresh')?.addEventListener('click', runAnalyze);
    document.getElementById('btn-export')?.addEventListener('click', exportData);
  } catch(e) { console.error('Account input handlers:', e); }

  const restored = await initSession();
  if (restored) {
    document.getElementById('key-input').value = restored;
    document.getElementById('key-input').placeholder = 'Session restored — click Analyze';
  }
});

function scrollToChar(charName) {
  const id = 'char-' + escHtml(charName).replace(/\s+/g, '-').toLowerCase();
  const card = document.getElementById(id);
  if (card) { card.scrollIntoView({ behavior: 'smooth', block: 'center' }); card.classList.add('highlight'); }
}

function selectTree(id) {
  document.querySelectorAll('.tn-item').forEach(n => n.classList.remove('selected'));
  const node = document.getElementById('tn-' + id);
  if (node) node.classList.add('selected');
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
  const refresh = Date.now();
  try {
    const r1 = await fetch(`/api/account/overview?api_key=${encKey}&lite=true&refresh=${refresh}`, { signal });
    if (!r1.ok) { const e = await r1.json().catch(() => ({detail:`HTTP ${r1.status}`})); throw new Error(Array.isArray(e.detail)?e.detail.map(x=>x.msg||JSON.stringify(x)).join('; '):(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))); }
    const l = await r1.json();
    showLoading(false);
    renderLite(l);
    showStatusBadge('active');
    const r2 = await fetch(`/api/account/overview?api_key=${encKey}&refresh=${refresh}`, { signal });
    if (!r2.ok) { const e = await r2.json().catch(() => ({detail:`HTTP ${r2.status}`})); throw new Error(Array.isArray(e.detail)?e.detail.map(x=>x.msg||JSON.stringify(x)).join('; '):(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))); }
    _overviewData = await r2.json();
    renderFull(_overviewData);
  } catch (e) {
    if (e.name === 'AbortError') return;
    showLoading(false);
    console.error('Account page error:', e);
    showError(e.message || String(e));
    showStatusBadge('error');
  }
}

function renderLite(data) {
  document.getElementById('key-section').style.display = 'none';
  document.getElementById('layer-overview').classList.remove('hidden');
  document.getElementById('layer-content').classList.remove('hidden');
  document.getElementById('layer-footer').classList.remove('hidden');
  const a = data.account || {};
  const k = data.kpis || {};
  document.getElementById('header-account-name').textContent = a.name || '—';
  document.getElementById('header-last-sync').textContent = 'Loading…';
  document.getElementById('ov-total-value').textContent = '…';
  document.getElementById('ov-liquid-value').textContent = '…';
  document.getElementById('ov-hidden-wealth').textContent = '…';
  document.getElementById('overview-progress').innerHTML = `
    <div class="ov-stat"><span class="ov-stat-lbl">Skins</span><span class="ov-stat-val">${k.skin_count||0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">Masteries</span><span class="ov-stat-val">${k.mastery_count||0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">Fractal</span><span class="ov-stat-val">${k.fractal_level||0}</span></div>
    <div class="ov-stat"><span class="ov-stat-lbl">WvW Rank</span><span class="ov-stat-val">${k.wvw_rank||0}</span></div>`;
  const gd = document.getElementById('graph-detail');
  if (gd) gd.innerHTML = '<div class="gd-empty">Loading account data…</div>';
}

function renderFull(data) {
  _activeTab = 'economy';
  _activeSub = null;
  const k = data.kpis || {};
  document.getElementById('header-last-sync').textContent = `Last sync: ${data.snapshot_time||'just now'}`;
  document.getElementById('ov-total-value').textContent = fmtCoin(k.account_value||0);
  document.getElementById('ov-liquid-value').textContent = fmtCoin(k.liquid_sell_after_fee||0);
  document.getElementById('ov-hidden-wealth').textContent = fmtCoin(k.hidden_wealth||0);

  try { renderTree(data); } catch(e) { console.error('renderTree:', e); }
  try { renderDetail(data); } catch(e) { console.error('renderDetail:', e); }
  try { renderOverlay(k); } catch(e) { console.error('renderOverlay:', e); }
}

/* ───────── Tree ───────── */

function renderTree(data) {
  const tree = document.getElementById('explorer-tree');
  if (!tree) return;
  const charItems = (data.characters||[]).map(c => {
    const cid = escHtml(c.name).replace(/\s+/g,'-').toLowerCase();
    return `<div class="tn-item tn-grandchild${_activeSub===escHtml(c.name)?' selected':''}" data-tab="characters" data-sub="${escHtml(c.name)}" id="tn-char-${cid}"><span class="tn-icon">⛨</span><span class="tn-label">${escHtml(c.name)}</span></div>`;
  }).join('');
  let html = `<div class="tn-section">Account<span class="tn-spacer"></span><span class="tn-expand-btn" id="tn-expand-all" title="Expand all">⊕</span><span class="tn-expand-btn" id="tn-collapse-all" title="Collapse all">⊖</span></div>`;
  for (const [key, val] of Object.entries(TREE)) {
    const expanded = _activeTab === key;
    html += `<div class="tn-item tn-root ${_activeTab===key?'expanded':''} ${_activeTab===key?'selected':''}" data-tab="${key}" id="tn-${key}"><svg class="tn-svg" width="16" height="16"><use href="#${val.icon}"/></svg><span class="tn-label">${val.label}</span><span class="tn-toggle">${_activeTab===key?'⊖':'⊕'}</span></div>`;
    if (expanded && val.sub.length) {
      val.sub.forEach(s => {
        html += `<div class="tn-item tn-child ${_activeSub===s.id?'selected':''}" data-tab="${key}" data-sub="${s.id}" id="tn-sub-${s.id}"><svg class="tn-svg" width="14" height="14"><use href="#${s.icon}"/></svg><span class="tn-label">${s.label}</span></div>`;
      });
    }
    if (key === 'characters' && expanded) html += charItems;
  }
  tree.innerHTML = html;

  tree.querySelectorAll('.tn-item').forEach(el => {
    el.addEventListener('click', e => {
      e.stopPropagation();
      const tab = el.dataset.tab;
      const sub = el.dataset.sub || null;
      const root = TREE[tab];
      if (root && root.sub && root.sub.length && sub === null && el.classList.contains('tn-root')) {
        _activeTab = _activeTab === tab ? null : tab;
        _activeSub = null;
      } else {
        _activeTab = tab;
        _activeSub = sub;
      }
      updateTreeSelection(data);
      renderDetail(data);
      if (sub && TREE.characters && tab === 'characters') scrollToChar(sub);
    });
  });

  document.getElementById('tn-collapse-all')?.addEventListener('click', e => {
    e.stopPropagation();
    _activeTab = null;
    _activeSub = null;
    updateTreeSelection(data);
    renderDetail(data);
  });
  document.getElementById('tn-expand-all')?.addEventListener('click', e => {
    e.stopPropagation();
    _activeTab = 'economy';
    _activeSub = null;
    updateTreeSelection(data);
    renderDetail(data);
  });
}

function updateTreeSelection(data) {
  const tree = document.getElementById('explorer-tree');
  if (!tree) return;
  // Update classes on existing DOM nodes without full re-render
  tree.querySelectorAll('.tn-item').forEach(el => {
    const tab = el.dataset.tab;
    const sub = el.dataset.sub || null;
    el.classList.toggle('selected',
      tab === _activeTab && (sub === null ? _activeSub === null : sub === _activeSub)
    );
  });
  // Update root expanded state (show/hide children)
  for (const [key, val] of Object.entries(TREE)) {
    const rootEl = document.getElementById('tn-' + key);
    if (!rootEl) continue;
    const toggle = rootEl.querySelector('.tn-toggle');
    if (toggle) toggle.textContent = _activeTab === key ? '⊖' : '⊕';
    // Show/hide child items via CSS class
    rootEl.classList.toggle('expanded', _activeTab === key);
    // Actually toggle sub-node visibility in the DOM
    if (key === 'characters') {
      // For characters, the grandchild items need to be shown/hidden
      let sibling = rootEl.nextElementSibling;
      while (sibling && sibling.classList.contains('tn-grandchild')) {
        sibling.style.display = _activeTab === key ? '' : 'none';
        sibling = sibling.nextElementSibling;
      }
    } else {
      // For other roots, toggle child items
      let sibling = rootEl.nextElementSibling;
      while (sibling && sibling.classList.contains('tn-child')) {
        sibling.style.display = _activeTab === key ? '' : 'none';
        sibling = sibling.nextElementSibling;
      }
    }
  }
}

/* ───────── Detail ───────── */

function renderDetail(data) {
  const gd = document.getElementById('graph-detail');
  if (!gd) return;

  if (!_activeTab) {
    gd.innerHTML = '<div class="gd-empty">Select a node from the Object Graph to inspect.</div>';
    return;
  }

  try {
    if (_activeTab === 'economy') renderEconomyDetail(data, _activeSub);
    else if (_activeTab === 'progress') renderProgressDetail(data, _activeSub);
    else if (_activeTab === 'collection') renderCollectionDetail(data, _activeSub);
    else if (_activeTab === 'characters') renderCharactersDetail(data, _activeSub);
  } catch(e) { console.error('renderDetail dispatch:', e); gd.innerHTML = '<div class=gd-empty>Render error: '+e.message+'</div>'; }
}

function renderEconomyDetail(data, sub) {
  const assets = data.assets || [];
  const ad = data.additional_data || {};
  const k = data.kpis || {};
  let items = assets;
  if (sub) { const target = CATEGORY_MAP[sub]; if (target) items = items.filter(a => a.category.toLowerCase() === target); }

  const totalValue = items.reduce((s,a) => s + (a.total_value||0), 0);
  const totalPct = items.reduce((s,a) => s + (a.percentage||0), 0);
  const isFiltered = !!sub;
  const subName = sub ? sub.charAt(0).toUpperCase() + sub.slice(1) : null;

  let html = `<div class="gd-head"><div><div class="gd-kicker">Economy${isFiltered ? ` / ${subName}` : ''}</div><h2>${subName || 'All Assets'}</h2><p>${isFiltered ? `Showing ${subName} details.` : 'Your account wealth across all storage locations.'}</p></div><span class="gd-status">${fmtCoin(totalValue)}</span></div>`;

  if (!isFiltered) {
    html += `<div class="gd-metrics">
      <div class="gd-metric"><span>Total Value</span><strong>${fmtCoin(k.account_value||0)}</strong></div>
      <div class="gd-metric"><span>Liquid Value</span><strong>${fmtCoin(k.liquid_sell_after_fee||0)}</strong></div>
      <div class="gd-metric"><span>Wallet Gold</span><strong>${fmtCoin(k.wallet_gold||0)}</strong></div>
      <div class="gd-metric"><span>Categories</span><strong>${assets.length}</strong></div>
    </div>`;
  }

  html += `<div class="gd-section"><h3>${isFiltered ? subName : 'Category'} Breakdown</h3><div class="gd-table">`;
  items.forEach(a => {
    const key = a.category.toLowerCase().replace(/\s+/g,'');
    html += `<div class="econ-row expanded" data-cat="${a.category}"><div class="econ-header" onclick="this.closest('.econ-row').classList.toggle('expanded')">
      <div class="econ-info"><span class="econ-toggle">▶</span><span class="econ-cat">${a.category}</span><span class="econ-pct">${a.percentage}%</span></div>
      <div class="econ-vals"><span class="econ-val">${fmtCoin(a.total_value||0)}</span><span class="econ-sub">${a.risk_flag}</span></div>
    </div><div class="econ-detail">
      <div class="econ-detail-row"><span>Items</span><span>${a.count||0}</span></div>
      <div class="econ-detail-row"><span>Distinct</span><span>${a.distinct_count||a.count||0}</span></div>
      <div class="econ-detail-row"><span>Avg Value</span><span>${a.count?fmtCoin(Math.round(a.total_value/a.count)):'—'}</span></div>
    </div></div>`;
  });
  html += `</div></div>`;

  if (ad.wallet_currencies && !isFiltered) {
    html += `<div class="gd-section"><h3>Wallet Currencies</h3><div class="gd-breakdown">`;
    (ad.wallet_currencies||[]).forEach(c => {
      const names = {1:'Gold',2:'Karma',3:'Laurels',4:'Spirit Shards'};
      html += `<div><span>${names[c.id]||'Currency #'+c.id}</span><strong>${c.id===1?fmtCoin(c.value):(c.value||0).toLocaleString()}</strong></div>`;
    });
    html += `</div></div>`;
  }
  document.getElementById('graph-detail').innerHTML = html;
}

function renderProgressDetail(data, sub) {
  const k = data.kpis || {};
  const ad = data.additional_data || {};
  const milestones = [
    {id:'fractals', label:'Fractal Level', value:k.fractal_level||0, max:150},
    {id:'wvw', label:'WvW Rank', value:k.wvw_rank||0, max:300},
    {id:'pvp', label:'PvP Rank', value:ad.pvp_rank||0, max:100},
    {id:'achievements', label:'AP (Daily)', value:k.daily_ap||0, max:10000},
    {id:'masteries', label:'AP (Monthly)', value:k.monthly_ap||0, max:5000},
    {id:'masteries2', label:'Masteries', value:k.mastery_count||0, max:90},
    {id:'builds', label:'Build Templates', value:ad.build_storage_count||0, max:30},
  ];

  let filtered = milestones;
  if (sub) filtered = milestones.filter(m => m.id === sub || m.id.startsWith(sub));

  const isFiltered = !!sub;
  const subName = sub ? sub.charAt(0).toUpperCase() + sub.slice(1) : null;

  let html = `<div class="gd-head"><div><div class="gd-kicker">Progression${isFiltered ? ' / ' + subName : ''}</div><h2>${subName || 'Account Progress'}</h2><p>${isFiltered ? `Focus on ${subName} metrics.` : 'Your achievement, mastery, and rank progress.'}</p></div><span class="gd-status">${k.achievement_count||0} Achievements</span></div>`;

  html += `<div class="gd-metrics">
    <div class="gd-metric"><span>Total AP</span><strong>${((k.daily_ap||0)+(k.monthly_ap||0)).toLocaleString()}</strong></div>
    <div class="gd-metric"><span>Masteries</span><strong>${k.mastery_count||0}</strong></div>
    <div class="gd-metric"><span>Fractal</span><strong>${k.fractal_level||0}</strong></div>
    <div class="gd-metric"><span>Characters</span><strong>${k.character_count||0}</strong></div>
  </div>`;

  html += `<div class="gd-section"><h3>Milestones</h3><div class="gd-table">`;
  filtered.forEach(m => {
    const pct = Math.min(100, (m.value / m.max) * 100);
    html += `<div class="gd-row"><span>${m.label}</span><span><div class="pm-bar"><div class="pm-fill" style="width:${pct}%"></div></div></span><span>${m.value}</span><span>/${m.max}</span></div>`;
  });
  html += `</div></div>`;
  document.getElementById('graph-detail').innerHTML = html;
}

function renderCollectionDetail(data, sub) {
  const k = data.kpis || {};
  const ad = data.additional_data || {};
  const items = [
    {id:'skins', label:'Skins', count:k.skin_count||0},
    {id:'dyes', label:'Dyes', count:ad.unlocked_dyes||0},
    {id:'minis', label:'Minis', count:ad.unlocked_minis||0},
    {id:'finishers', label:'Finishers', count:ad.finisher_count||data.object_graph?.unlock_counts?.finishers||0},
  ];
  let filtered = items;
  if (sub) filtered = items.filter(i => i.id === sub);

  const isFiltered = !!sub;
  const subName = sub ? sub.charAt(0).toUpperCase() + sub.slice(1) : null;
  const total = items.reduce((s,i) => s + i.count, 0);

  let html = `<div class="gd-head"><div><div class="gd-kicker">Collections${isFiltered ? ' / ' + subName : ''}</div><h2>${subName || 'All Unlocks'}</h2><p>${isFiltered ? `${subName} unlock details.` : 'Your collection progress across all categories.'}</p></div><span class="gd-status">${total} Total</span></div>`;

  html += `<div class="gd-metrics">`;
  items.forEach(i => {
    const highlight = sub && sub === i.id;
    html += `<div class="gd-metric" style="${highlight?'border-color:#c8956c':''}"><span>${i.label}</span><strong>${i.count}</strong></div>`;
  });
  html += `</div></div>`;
  document.getElementById('graph-detail').innerHTML = html;
}

function renderCharactersDetail(data, sub) {
  const chars = data.characters || [];
  const k = data.kpis || {};
  let filtered = chars;
  if (sub) filtered = chars.filter(c => c.name.toLowerCase() === sub.toLowerCase());

  const isFiltered = !!sub;
  const subName = sub || null;
  const profColors = { Guardian:'#6b8', Necromancer:'#86a', Elementalist:'#c84', Mesmer:'#a6c', Warrior:'#c86', Revenant:'#a60', Ranger:'#8a6', Thief:'#888', Engineer:'#a86' };

  let html = `<div class="gd-head"><div><div class="gd-kicker">Characters${isFiltered ? ' / ' + subName : ''}</div><h2>${subName || 'All Characters'}</h2><p>${isFiltered ? `Details for ${subName}.` : `${chars.length} characters on this account.`}</p></div><span class="gd-status">${k.character_count||0} Total</span></div>`;

  if (!chars.length) {
    html += `<div class="gd-empty">No characters found.</div>`;
    document.getElementById('graph-detail').innerHTML = html;
    return;
  }

  html += `<div class="gd-section"><div class="char-cards">`;
  filtered.forEach(c => {
    const color = profColors[c.profession] || '#888';
    const cid = 'char-'+escHtml(c.name).replace(/\s+/g,'-').toLowerCase();
    html += `<div class="char-card" id="${cid}" style="border-left:3px solid ${color}">
      <div class="char-top" onclick="document.getElementById('${cid}').classList.toggle('expanded')">
        <span class="char-name">${escHtml(c.name)}</span>
        <span class="char-prof">${c.profession}</span>
        <span class="char-lv">Lv${c.level}</span>
        <span style="font-size:10px;color:#555;margin-left:auto">▼</span>
      </div>
      <div class="char-meta"><span>${c.playtime||'—'}</span><span>${c.gear_value?fmtCoin(c.gear_value):'—'}</span><span>${c.build_status||'—'}</span></div>
      <div class="char-login">${c.last_login||'—'}</div>
      <div class="char-expand"><div class="char-eq-note">Equipment slots and inventory detail available with item-level data.</div></div>
    </div>`;
  });
  html += `</div></div>`;
  document.getElementById('graph-detail').innerHTML = html;
}

/* ───────── Overlay ───────── */

function renderOverlay(k) {
  const body = document.getElementById('ai-overlay-body');
  if (!body) return;
  body.innerHTML = `
    <div class="ai-oi"><div class="ai-oi-label">Hidden Wealth</div><div class="ai-oi-value">${fmtCoin(k.hidden_wealth||0)}</div><div class="ai-oi-sub">Unused value in materials, bank, etc.</div></div>
    <div class="ai-oi"><div class="ai-oi-label">Build Ready</div><div class="ai-oi-value">${k.build_ready_count??'—'} / ${k.character_count||0}</div><div class="ai-oi-sub">Characters near meta-ready state</div></div>
    <div class="ai-oi"><div class="ai-oi-label">Liquid Value</div><div class="ai-oi-value">${fmtCoin(k.liquid_sell_after_fee||0)}</div><div class="ai-oi-sub">Sell value after TP fees</div></div>`;
}

/* ───────── Utils ───────── */

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
  const b = document.getElementById('api-status-badge');
  if (!b) return;
  b.dataset.status = status;
  b.textContent = {active:'● Active',stale:'● Stale',error:'● Error'}[status]||'● Unknown';
}

function exportData() {
  if (!_overviewData) return;
  const d = { exported_at:new Date().toISOString(), account:_overviewData.account, kpis:_overviewData.kpis, assets:_overviewData.assets, characters:_overviewData.characters };
  const b = new Blob([JSON.stringify(d,null,2)], {type:'application/json'});
  const u = URL.createObjectURL(b);
  const a = document.createElement('a');
  a.href = u;
  a.download = `gw2-account-${d.account?.name||'unknown'}-${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(u);
}

function escHtml(s) { if (!s) return ''; return String(s).replace(/[&<>"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[m]||m); }

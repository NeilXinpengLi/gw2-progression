const MAX_CACHE_SIZE = 5000;

const _itemCache    = {};
const _currencyCache= {};
const _matCatCache  = {};
const _masteryCache = {};
const _mapCache     = {};
const _skinCache    = {};
const _colorCache   = {};
const _guildCache   = {};

let _valueData = null;
let _valueCharts = {};

async function backendResolve(type, ids) {
  const res = await fetch('/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, ids: ids.map(String) }),
  });
  if (!res.ok) return [];
  return res.json();
}

async function backendResolveSingle(type, id) {
  const res = await fetch('/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, id: String(id) }),
  });
  if (!res.ok) return null;
  return res.json();
}

function cappedCacheAdd(cache, key, val) {
  if (Object.keys(cache).length >= MAX_CACHE_SIZE) {
    const oldest = Object.keys(cache)[0];
    delete cache[oldest];
  }
  cache[key] = val;
}

async function resolveItems(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _itemCache));
  if (!missing.length) return;
  const data = await backendResolve('items', missing);
  for (const item of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_itemCache, item.id, { name: item.name, icon: item.icon });
  }
}

async function resolveCurrencies(ids) {
  const missing = [...new Set(ids)].filter(id => !(id in _currencyCache));
  if (!missing.length) return;
  const data = await backendResolve('currencies', missing);
  for (const c of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_currencyCache, c.id, { name: c.name, description: c.description });
  }
}

async function resolveMatCategories() {
  if (Object.keys(_matCatCache).length) return;
  const data = await backendResolve('materials', []);
  for (const cat of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_matCatCache, cat.id, cat.name);
  }
}

async function resolveMasteries(ids) {
  const missing = [...new Set(ids)].filter(id => !(id in _masteryCache));
  if (!missing.length) return;
  const data = await backendResolve('masteries', missing);
  for (const m of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_masteryCache, m.id, { name: m.name, region: m.region });
  }
}

async function resolveMaps(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _mapCache));
  if (!missing.length) return;
  const data = await backendResolve('maps', missing);
  for (const m of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_mapCache, m.id, m.name);
  }
}

async function resolveSkins(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _skinCache));
  if (!missing.length) return;
  const data = await backendResolve('skins', missing);
  for (const s of (Array.isArray(data) ? data : [])) {
    const subtype = s.details?.type || s.details?.weight_class || '';
    cappedCacheAdd(_skinCache, s.id, { name: s.name, icon: s.icon, type: s.type, subtype });
  }
}

async function resolveGuilds(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _guildCache));
  await Promise.all(missing.map(async id => {
    const data = await backendResolveSingle('guild', id);
    cappedCacheAdd(_guildCache, id, data ? { name: data.name, tag: data.tag } : { name: 'Unknown Guild', tag: '?' });
  }));
}

async function resolveColors(ids) {
  const missing = [...new Set(ids)].filter(id => id != null && !(id in _colorCache));
  if (!missing.length) return;
  const data = await backendResolve('colors', missing);
  for (const c of (Array.isArray(data) ? data : [])) {
    const rgb = c.cloth?.rgb || c.leather?.rgb || c.metal?.rgb || [128, 128, 128];
    cappedCacheAdd(_colorCache, c.id, { name: c.name, hex: rgbToHex(rgb) });
  }
}

async function resolveSearch(query) {
  const res = await fetch('/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'search_items', query: String(query) }),
  });
  if (!res.ok) return [];
  return res.json();
}

function rgbToHex([r, g, b]) {
  return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
}

function itemName(id)    { return _itemCache[id]?.name    || `Item #${id}`; }
function itemIcon(id)    { return _itemCache[id]?.icon    || null; }
function currencyName(id){ return _currencyCache[id]?.name || `Currency #${id}`; }
function matCatName(id)  { return _matCatCache[id]        || `Category #${id}`; }
function masteryName(id) { return _masteryCache[id]?.name || `Mastery #${id}`; }
function masteryRegion(id){ return _masteryCache[id]?.region || '—'; }
function mapName(id)     { return _mapCache[id]           || `Map #${id}`; }
function skinName(id)    { return _skinCache[id]?.name    || `Skin #${id}`; }
function skinIcon(id)    { return _skinCache[id]?.icon    || null; }
function colorHex(id)    { return id != null ? (_colorCache[id]?.hex || '#888') : null; }

function fmtCoin(copper) {
  if (!copper) return '0g 0s 0c';
  const sign = copper < 0 ? '-' : '';
  const abs = Math.abs(copper);
  return `${sign}${Math.floor(abs/10000)}g ${Math.floor((abs%10000)/100)}s ${abs%100}c`;
}

function fmtCoinShort(copper) {
  if (!copper) return '0g';
  const abs = Math.abs(copper);
  const g = Math.floor(abs / 10000);
  const s = Math.floor((abs % 10000) / 100);
  if (g > 0) return `${g}g`;
  if (s > 0) return `${s}s`;
  return `${abs}c`;
}

// ── Tab switching ──
document.getElementById('nav-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#nav-tabs button').forEach(b => {
    b.classList.remove('active');
    b.setAttribute('aria-selected', 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  btn.setAttribute('aria-selected', 'true');
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');

  // Lazily render charts when value tab is first shown
  if (btn.dataset.tab === 'value' && _valueData && !_valueCharts._rendered) {
    renderValueCharts(_valueData);
  }
});

// ── Analyze ──
document.getElementById('analyze-btn').addEventListener('click', runAnalyze);
document.getElementById('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') runAnalyze(); });

let _accountData = null;
let _abortController = null;
let _sessionToken = null;

async function runAnalyze() {
  const rawKey = document.getElementById('key-input').value.trim();
  if (!rawKey) {
    const msg = document.getElementById('status-msg');
    msg.className = 'error';
    msg.textContent = 'Please paste a GW2 API key first.';
    return;
  }
  if (_abortController) _abortController.abort();
  _abortController = new AbortController();
  let signal = _abortController.signal;
  const btn = document.getElementById('analyze-btn');
  const msg = document.getElementById('status-msg');
  btn.disabled = true;
  msg.className = '';
  let useKey = rawKey;

  // Use existing session token if available, otherwise create a new session
  if (_sessionToken) {
    useKey = _sessionToken;
    msg.innerHTML = '<span class="spinner"></span> Restoring session…';
  } else {
    msg.innerHTML = '<span class="spinner"></span> Creating session…';
    try {
      const sessionRes = await fetch('/auth/session', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ api_key: rawKey }), signal,
      });
      if (sessionRes.ok) {
        const session = await sessionRes.json();
        _sessionToken = session.token;
        useKey = session.token;
        msg.innerHTML = `<span class="spinner"></span> Session created for ${session.account_name}. Fetching data…`;
        loadAccountSelector();
      }
    } catch(e) {
      msg.innerHTML = '<span class="spinner"></span> Session creation failed, using direct auth…';
    }
  }

  if (_abortController) _abortController.abort();
  _abortController = new AbortController();
  signal = _abortController.signal;

  try {
    document.querySelectorAll('.tab-loading').forEach(el => el.remove());
    document.querySelectorAll('.tab-error').forEach(el => el.innerHTML = '');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('nav-tabs').classList.add('hidden');
    msg.className = '';
    msg.innerHTML = '<span class="spinner"></span> Fetching account data…';

    const [analyzeRes, valueRes] = await Promise.all([
      fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: useKey }),
        signal,
      }),
      fetch('/value/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: useKey }),
        signal,
      }),
    ]);

    if (!analyzeRes.ok) {
      const err = await analyzeRes.json().catch(() => ({}));
      if (analyzeRes.status === 422) {
        const detail = err.detail?.[0]?.msg || err.detail || 'Invalid request.';
        throw new Error(detail);
      }
      throw new Error(err.detail || `HTTP ${analyzeRes.status}`);
    }

    const data = await analyzeRes.json();
    _accountData = data;

    if (valueRes.ok) {
      _valueData = await valueRes.json();
    } else {
      _valueData = null;
      msg.innerHTML += ' <span class="warning-text">Value analysis failed (check API key permissions).</span>';
    }

    msg.innerHTML = '<span class="spinner"></span> Resolving names…';

    const matIds    = (data.materials || []).filter(m => m.count > 0).map(m => m.id);
    const bankIds   = (data.bank || []).filter(Boolean).map(s => s.id);
    const walletIds = (data.wallet || []).map(w => w.id);
    const masteryIds= (data.masteries || []).map(m => m.id);
    const mapIds    = (data.pvp_games || []).map(g => g.map_id).filter(Boolean);

    const equipSkinIds = [], equipItemIds = [], dyeIds = [], guildIds = [];
    for (const ch of (data.characters || [])) {
      if (ch.guild) guildIds.push(ch.guild);
      for (const eq of (ch.equipment || [])) {
        equipItemIds.push(eq.id);
        if (eq.skin) equipSkinIds.push(eq.skin);
        for (const d of (eq.dyes || [])) { if (d != null) dyeIds.push(d); }
      }
    }

    // Also resolve item IDs from valuation data
    const valueItemIds = [];
    if (_valueData) {
      for (const item of (_valueData.top_items || [])) {
        valueItemIds.push(item.item_id);
      }
      // Collect first 200 holding IDs for display
      for (const h of (_valueData.holdings || []).slice(0, 200)) {
        valueItemIds.push(h.item_id);
      }
    }

    await Promise.all([
      resolveItems([...matIds, ...bankIds, ...equipItemIds, ...valueItemIds]),
      resolveCurrencies(walletIds),
      resolveMatCategories(),
      resolveMasteries(masteryIds),
      resolveMaps(mapIds),
      resolveSkins(equipSkinIds),
      resolveColors(dyeIds),
      resolveGuilds(guildIds),
    ]);

    msg.textContent = `Loaded data for ${data.account_name}`;
    // Save to localStorage
    if (_sessionToken) {
      try { localStorage.setItem('gw2_session', _sessionToken); } catch(e) {}
    }
    renderAll(data);
  } catch (e) {
    if (e.name === 'AbortError') return;
    msg.className = 'error';
    if (e.message === 'Failed to fetch') {
      msg.textContent = 'Error: Unable to reach the server. Is it running on port 8000?';
    } else {
      msg.textContent = `Error: ${e.message}`;
    }
  } finally {
    btn.disabled = false;
  }
}

// ── Account Management ──
async function loadAccountSelector() {
  const sel = document.getElementById('account-selector');
  try {
    const res = await fetch('/auth/sessions');
    if (!res.ok) return;
    const sessions = await res.json();
    if (sessions.length > 1) {
      sel.classList.remove('hidden');
      sel.innerHTML = '<option value="">Switch account…</option>' +
        sessions.map(s => `<option value="${s.token}">${s.account_name}</option>`).join('');
      sel.onchange = () => {
        if (sel.value) {
          localStorage.setItem('gw2_session', sel.value);
          location.reload();
        }
      };
    }
  } catch(e) { /* ignore */ }
}

// Restore session on page load and auto-analyze
(function() {
  try {
    const saved = localStorage.getItem('gw2_session');
    if (saved) {
      _sessionToken = saved;
      document.getElementById('key-input').value = saved;
      const analyzeBtn = document.getElementById('analyze-btn');
      if (analyzeBtn && !analyzeBtn.disabled) {
        setTimeout(runAnalyze, 300);
      }
    }
  } catch(e) {}
})();

function renderAll(d) {
  document.querySelectorAll('.tab-loading').forEach(el => el.remove());
  document.getElementById('results').classList.remove('hidden');
  document.getElementById('nav-tabs').classList.remove('hidden');
  renderOverview(d);
  renderValue(_valueData);
  renderCharacters(d.characters || []);
  renderWallet(d.wallet || []);
  renderInventory(d);
  renderProgression(d);
  renderPvp(d);
  renderUnlocks(d);
  renderWvw(d);
  renderBuilds(d);
  setupWardrobe(d.unlocked_skins || []);
  const exportBtn = document.getElementById('export-report-btn');
  if (exportBtn) exportBtn.disabled = false;
  loadReportHistory();
}

// ── Overview ──
function renderOverview(d) {
  const created = d.account_created ? new Date(d.account_created).toLocaleDateString() : '—';
  const cards = [
    { label: 'Account',       value: d.account_name || '—',              sub: `World ${d.account_world}` },
    { label: 'Created',       value: created,                            sub: 'account created' },
    { label: 'Playtime',      value: `${d.account_age_hours}h`,          sub: 'total hours' },
    { label: 'Fractal Level', value: d.fractal_level ?? '—',             sub: 'highest tier' },
    { label: 'Daily AP',      value: (d.daily_ap ?? 0).toLocaleString(), sub: 'achievement points' },
    { label: 'Monthly AP',    value: (d.monthly_ap ?? 0).toLocaleString(),sub: 'monthly achievements' },
    { label: 'WvW Rank',      value: d.wvw_rank ?? '—',                  sub: 'world vs world' },
    { label: 'Characters',    value: (d.characters || []).length,         sub: 'on account' },
    { label: 'Skins',         value: d.unlocked_skins_count ?? '—',      sub: 'unlocked' },
    { label: 'Dyes',          value: d.unlocked_dyes_count ?? '—',       sub: 'unlocked' },
  ];
  document.getElementById('overview-cards').innerHTML = cards.map(c => `
    <div class="stat-card">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
      <div class="sub">${c.sub}</div>
    </div>`).join('');

  const ALL_PERMS = ['account','builds','characters','guilds','inventories','progression','pvp','tradingpost','unlocks','wallet','wvw'];
  const granted = new Set();
  if (d.account_name) granted.add('account');
  if (d.characters) granted.add('characters');
  if (d.wallet) granted.add('wallet');
  if (d.bank) granted.add('inventories');
  if (d.achievements) granted.add('progression');
  if (d.builds) granted.add('builds');
  if (d.pvp_stats) granted.add('pvp');
  if (d.tradingpost_buys !== null) granted.add('tradingpost');
  if (d.unlocked_skins_count !== null) granted.add('unlocks');
  if (d.wvw) granted.add('wvw');

  document.getElementById('perm-grid').innerHTML = ALL_PERMS.map(p => `
    <span class="perm-badge ${granted.has(p) ? 'granted' : 'missing'}">
      ${granted.has(p) ? '✓' : '✗'} ${p}
    </span>`).join('');

  const KNOWN_LIMITATIONS = {
    guilds: 'Guild details are only accessible to guild leaders via the GW2 API. Members can see their guild IDs on the account but not guild data.',
  };

  const ERR_TAB_MAP = {
    account:           'err-overview',
    builds:            'err-overview',
    tradingpost_buys:  'err-overview',
    tradingpost_sells: 'err-overview',
    characters:        'err-characters',
    wallet:            'err-wallet',
    bank:              'err-inventory',
    materials:         'err-inventory',
    shared_inventory:  'err-inventory',
    achievements:      'err-progression',
    masteries:         'err-progression',
    mastery_points:    'err-progression',
    pvp_stats:         'err-pvp',
    pvp_games:         'err-pvp',
    pvp_standings:     'err-pvp',
    builds:            'err-builds',
    skins:             'err-skins',
    dyes:              'err-unlocks',
    minis:             'err-unlocks',
    finishers:         'err-unlocks',
    wvw:               'err-overview',
  };

  const errs = d.errors || {};
  Object.entries(errs).forEach(([k, v]) => {
    if (KNOWN_LIMITATIONS[k]) return;
    const tabId = ERR_TAB_MAP[k] || 'err-overview';
    const el = document.getElementById(tabId);
    if (el) el.innerHTML += `<div class="error-box"><strong>${k}</strong>: ${v}</div>`;
  });
  Object.entries(errs).forEach(([k]) => {
    if (!KNOWN_LIMITATIONS[k]) return;
    const el = document.getElementById('err-overview');
    if (el) el.innerHTML += `
      <div style="background:#1a1a2a;border:1px solid #334;border-radius:4px;padding:12px 16px;margin-top:8px;color:var(--text-dim);font-size:13px">
        <strong style="color:var(--gold)">ℹ ${k}</strong> — ${KNOWN_LIMITATIONS[k]}
      </div>`;
  });
}

// Characters, Wardrobe, Wallet, Inventory, Progression, PvP, Unlocks, WvW, Builds moved to app-characters.js
// ── Holdings toggle & filter ──
// ── Goals ──
document.getElementById('goals-create-btn').addEventListener('click', createGoal);
document.getElementById('goals-target').addEventListener('keydown', e => { if (e.key === 'Enter') createGoal(); });

async function loadGoals() {
  const accountName = _accountData?.account_name;
  if (!accountName) { document.getElementById('goals-cards').innerHTML = '<div class="dim">Run analysis first.</div>'; return; }

  try {
    const res = await fetch(`/goals?account_name=${encodeURIComponent(accountName)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const goals = await res.json();
    document.getElementById('goals-list').classList.remove('hidden');

    if (!goals.length) {
      document.getElementById('goals-cards').innerHTML = '<div class="dim">No goals yet. Create one above.</div>';
      return;
    }

    // Resolve item names
    const ids = [...new Set(goals.map(g => g.target_item_id))];
    await resolveItems(ids);

    document.getElementById('goals-cards').innerHTML = goals.map(g => {
      const name = itemName(g.target_item_id) || `Item #${g.target_item_id}`;
      const icon = itemIcon(g.target_item_id);
      const img = icon ? `<img src="${icon}" width="28" height="28" style="vertical-align:middle;margin-right:8px;border-radius:3px">` : '';
      const pct = g.completion_percent || 0;
      const pctColor = pct >= 100 ? '#6bc46b' : pct >= 50 ? '#d0a050' : '#c07070';
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:14px;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          ${img}
          <div style="flex:1">
            <span style="color:var(--gold-light);font-weight:600">${name}</span>
            <span class="dim"> ×${g.target_count}</span>
          </div>
          <span class="perm-badge ${g.status === 'active' ? 'granted' : 'missing'}">${g.status}</span>
          <span style="color:var(--text-dim);font-size:11px">${g.priority}</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-bottom:8px">
          <div><span class="dim" style="font-size:11px">Completion</span><br><span style="font-size:18px;font-weight:600;color:${pctColor}">${pct}%</span></div>
          <div><span class="dim" style="font-size:11px">Owned Value</span><br><span class="gold-val" style="font-size:16px">${fmtCoinShort(g.owned_material_value)}</span></div>
          <div><span class="dim" style="font-size:11px">Remaining Cost</span><br><span class="gold-val" style="font-size:16px">${fmtCoinShort(g.estimated_remaining_cost)}</span></div>
          <div><span class="dim" style="font-size:11px">Missing Items</span><br><span style="font-size:16px">${g.missing_item_count}</span></div>
        </div>
        <div style="background:var(--bg3);border-radius:3px;height:6px;overflow:hidden;margin-bottom:8px">
          <div style="width:${Math.min(pct, 100)}%;height:100%;background:${pctColor};border-radius:3px;transition:width .5s"></div>
        </div>
        <div style="display:flex;gap:6px">
          <button class="goal-refresh-btn" data-id="${g.goal_id}" style="background:var(--bg3);border:1px solid var(--border);border-radius:3px;color:var(--text);cursor:pointer;font-size:12px;padding:4px 12px">⟳ Refresh</button>
          <button class="goal-delete-btn" data-id="${g.goal_id}" style="background:#2a1515;border:1px solid #5a2020;border-radius:3px;color:#c07070;cursor:pointer;font-size:12px;padding:4px 12px">✕ Delete</button>
        </div>
      </div>`;
    }).join('');

    // Attach event listeners
    document.querySelectorAll('.goal-refresh-btn').forEach(btn => {
      btn.addEventListener('click', () => refreshGoalUI(btn.dataset.id));
    });
    document.querySelectorAll('.goal-delete-btn').forEach(btn => {
      btn.addEventListener('click', () => deleteGoalUI(btn.dataset.id));
    });
  } catch (e) {
    document.getElementById('goals-cards').innerHTML = `<div class="dim">Error: ${e.message}</div>`;
  }
}

async function createGoal() {
  const target = parseInt(document.getElementById('goals-target').value);
  const qty = parseInt(document.getElementById('goals-qty').value) || 1;
  const priority = document.getElementById('goals-priority').value;
  const key = document.getElementById('key-input').value.trim();

  if (!key) { setGoalsStatus('error', 'Enter API key first.'); return; }
  if (!target) { setGoalsStatus('error', 'Enter a target item ID.'); return; }

  setGoalsStatus('', '<span class="spinner"></span> Creating goal…');
  try {
    const res = await fetch('/goals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key, target_item_id: target, target_count: qty, priority }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
    setGoalsStatus('ok', 'Goal created!');
    document.getElementById('goals-target').value = '';
    loadGoals();
  } catch (e) {
    setGoalsStatus('error', `Error: ${e.message}`);
  }
}

async function refreshGoalUI(goalId) {
  const key = document.getElementById('key-input').value.trim();
  if (!key) return;
  setGoalsStatus('', '<span class="spinner"></span> Refreshing…');
  try {
    const res = await fetch(`/goals/${goalId}/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
    setGoalsStatus('ok', 'Goal refreshed!');
    loadGoals();
  } catch (e) {
    setGoalsStatus('error', `Error: ${e.message}`);
  }
}

async function deleteGoalUI(goalId) {
  try {
    const res = await fetch(`/goals/${goalId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    loadGoals();
  } catch (e) {
    setGoalsStatus('error', `Error: ${e.message}`);
  }
}

function setGoalsStatus(cls, msg) {
  const el = document.getElementById('goals-status');
  el.className = cls === 'error' ? 'error' : '';
  el.innerHTML = msg;
}

// Load goals when tab is clicked
document.querySelectorAll('#nav-tabs button').forEach(btn => {
  if (btn.dataset.tab === 'goals') {
    btn.addEventListener('click', () => setTimeout(loadGoals, 100), { once: true });
  }
});

// ── Value Delta ──
async function loadValueDelta() {
  const section = document.getElementById('value-delta-section');
  const title = section.previousElementSibling;
  if (section.style.display === 'block') return; // already loaded

  const accountName = _accountData?.account_name;
  if (!accountName) {
    document.getElementById('value-delta-summary').innerHTML = '<div class="dim">No account data.</div>';
    return;
  }

  try {
    const res = await fetch(`/value/delta?account_name=${encodeURIComponent(accountName)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const delta = await res.json();
    if (delta.error) {
      document.getElementById('value-delta-summary').innerHTML = `<div class="dim">${delta.error}</div>`;
      return;
    }

    // Resolve item names for top gainers/decliners
    const ids = new Set();
    for (const d of [...(delta.top_gainers || []), ...(delta.top_decliners || [])]) {
      if (d.item_id) ids.add(d.item_id);
    }
    if (ids.size) await resolveItems([...ids]);

    const sign = delta.total_delta_buy >= 0 ? '+' : '';
    const cls = delta.total_delta_buy >= 0 ? 'vs-up' : 'vs-down';
    document.getElementById('value-delta-summary').innerHTML = `
      <div class="value-stat-box">
        <div class="vsl-label">Total Change</div>
        <div class="vsl-value ${cls}">${sign}${fmtCoinShort(delta.total_delta_buy)}</div>
      </div>
      <div class="value-stat-box">
        <div class="vsl-label">Price Effect</div>
        <div class="vsl-value vsl-small">${fmtCoinShort(delta.price_effect_delta)}</div>
      </div>
      <div class="value-stat-box">
        <div class="vsl-label">Quantity Effect</div>
        <div class="vsl-value vsl-small">${fmtCoinShort(delta.quantity_effect_delta)}</div>
      </div>
      <div class="value-stat-box">
        <div class="vsl-label">Period</div>
        <div class="vsl-value vsl-small">${delta.from_time?.slice(5,16)?.replace('T',' ') || '?'} → ${delta.to_time?.slice(5,16)?.replace('T',' ') || '?'}</div>
      </div>
    `;

    const gainers = document.getElementById('value-top-gainers');
    const decliners = document.getElementById('value-top-decliners');

    const renderDeltaList = (items, container, isGainer) => {
      if (!items || !items.length) {
        container.innerHTML = '<div class="dim">None</div>';
        return;
      }
      container.innerHTML = items.map(d => {
        const icon = itemIcon(d.item_id);
        const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
        const valCls = d.value_delta > 0 ? 'vs-up' : 'vs-down';
        const causeLabels = { quantity_change: 'Qty', price_change: 'Price', new_item: 'New', removed_item: 'Removed' };
        return `<div style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
          ${img}<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${itemName(d.item_id)}</span>
          <span style="color:var(--text-dim);font-size:10px">${causeLabels[d.primary_cause] || d.primary_cause}</span>
          <span class="${valCls}">${d.value_delta > 0 ? '+' : ''}${fmtCoinShort(d.value_delta)}</span>
        </div>`;
      }).join('');
    };

    renderDeltaList(delta.top_gainers, gainers, true);
    renderDeltaList(delta.top_decliners, decliners, false);
  } catch (e) {
    document.getElementById('value-delta-summary').innerHTML = `<div class="dim">Failed to load delta: ${e.message}</div>`;
  }
}

function toggleDelta() {
  const section = document.getElementById('value-delta-section');
  const title = section.previousElementSibling;
  const isHidden = section.style.display === 'none';
  section.style.display = isHidden ? 'block' : 'none';
  if (title) {
    const span = title.querySelector('span');
    if (span) span.innerHTML = (isHidden ? '▼' : '▶') + span.innerHTML.slice(1);
  }
  if (isHidden) loadValueDelta();
}

function toggleMaterials() {
  const section = document.getElementById('materials-section');
  const title = section.previousElementSibling;
  const isHidden = section.style.display === 'none';
  section.style.display = isHidden ? 'block' : 'none';
  if (title) {
    const span = title.querySelector('span');
    if (span) span.innerHTML = (isHidden ? '▼' : '▶') + ' Materials by Category';
  }
}

function renderHoldingsPage() {
  const data = window._allHoldings || [];
  const page = window._holdingsPage || 0;
  const pageSize = window._holdingsPageSize || 50;
  const q = document.getElementById('holdings-search').value.trim().toLowerCase();
  const loc = document.getElementById('holdings-location').value;
  const status = document.getElementById('holdings-status').value;

  const filtered = data.filter(h => {
    if (q) return String(h.item_id).includes(q);
    return true;
  }).filter(h => {
    if (loc) return h.location_type === loc;
    return true;
  }).filter(h => {
    if (status) return h.valuation_status === status;
    return true;
  });

  const totalFiltered = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const start = currentPage * pageSize;
  const pageItems = filtered.slice(start, start + pageSize);

  const tbody = document.querySelector('#holdings-table tbody');
  if (!pageItems.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="dim">No matching items</td></tr>';
  } else {
    tbody.innerHTML = pageItems.map(h => {
      const name = itemName(h.item_id);
      const icon = itemIcon(h.item_id);
      const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
      const locLabels = { material_storage: 'Mat Storage', bank: 'Bank', shared_inventory: 'Shared', tradingpost: 'TP', wallet: 'Wallet' };
      let locDisplay = locLabels[h.location_type] || h.location_type;
      // Extract character name from location_ref like "MyChar/bag0/slot0"
      if (h.location_type === 'character' && h.location_ref) {
        locDisplay = 'Char: ' + h.location_ref.split('/')[0];
      }
      let statusEl = `<span class="perm-badge granted">Priced</span>`;
      if (h.valuation_status === 'unpriced') statusEl = `<span class="perm-badge missing">Unpriced</span>`;
      if (h.valuation_status === 'account_bound') statusEl = `<span class="perm-badge missing">Bound</span>`;
      return `<tr data-item="${h.item_id}" data-loc="${h.location_type}" data-status="${h.valuation_status}">
        <td>${img}<span class="gold-val">${name}</span></td>
        <td>${h.count.toLocaleString()}</td>
        <td class="dim">${locDisplay}</td>
        <td class="gold-val">${h.value_buy ? fmtCoinShort(h.value_buy) : '—'}</td>
        <td class="gold-val">${h.value_sell ? fmtCoinShort(h.value_sell) : '—'}</td>
        <td>${statusEl}</td>
      </tr>`;
    }).join('');
  }

  document.getElementById('holdings-count-display').textContent =
    `${totalFiltered} items total (page ${currentPage + 1}/${totalPages})`;

  const pagination = document.getElementById('holdings-pagination');
  if (totalPages <= 1) {
    pagination.innerHTML = '';
    return;
  }
  let html = '<div style="display:flex;gap:6px;align-items:center;padding:10px 0;flex-wrap:wrap">';
  if (currentPage > 0) html += `<button class="page-btn" data-page="0">«</button><button class="page-btn" data-page="${currentPage - 1}">‹</button>`;
  for (let p = Math.max(0, currentPage - 2); p <= Math.min(totalPages - 1, currentPage + 2); p++) {
    html += `<button class="page-btn${p === currentPage ? ' page-active' : ''}" data-page="${p}">${p + 1}</button>`;
  }
  if (currentPage < totalPages - 1) html += `<button class="page-btn" data-page="${currentPage + 1}">›</button><button class="page-btn" data-page="${totalPages - 1}">»</button>`;
  html += '</div>';
  pagination.innerHTML = html;
  pagination.querySelectorAll('.page-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      window._holdingsPage = parseInt(btn.dataset.page);
      renderHoldingsPage();
    });
  });
}

function filterHoldings() {
  window._holdingsPage = 0;
  renderHoldingsPage();
}

// ── Report Export ──
async function exportReport() {
  const btn = document.getElementById('export-report-btn');
  const status = document.getElementById('export-status');
  const data = _accountData;
  if (!data) {
    status.textContent = 'Run analysis first.';
    return;
  }
  btn.disabled = true;
  status.innerHTML = '<span class="spinner"></span> Generating report…';

  const topItems = (_valueData?.top_items || []).slice(0, 10).map(i => ({
    item_id: i.item_id,
    name: itemName(i.item_id),
    count: i.count,
    value_buy: i.value_buy,
    value_sell: i.value_sell,
  }));

  const params = new URLSearchParams({
    account_name: data.account_name,
    report_type: 'full',
    title: `Account Report — ${data.account_name}`,
    summary: `Generated report for ${data.account_name} with ${(data.characters || []).length} characters.`,
    total_value_buy: _valueData?.summary?.total_value_buy || 0,
    total_value_sell: _valueData?.summary?.total_value_sell || 0,
    wallet_gold: (_valueData?.summary?.wallet_value || 0),
    character_count: (data.characters || []).length,
    goal_count: 0,
    goal_progress_pct: 0,
    build_readiness_pct: 0,
  });

  try {
    const res = await fetch(`/reports/generate?${params}`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const report = await res.json();
    status.textContent = `Report #${report.report_id} generated.`;
    setTimeout(() => { status.textContent = ''; }, 3000);
    loadReportHistory();
    // Enable download of raw report JSON
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gw2-report-${data.account_name}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  } finally {
    btn.disabled = false;
  }
}

async function loadReportHistory() {
  const data = _accountData;
  if (!data) return;
  const container = document.getElementById('report-history');
  const list = document.getElementById('report-list');
  try {
    const res = await fetch(`/reports?account_name=${encodeURIComponent(data.account_name)}&limit=10`);
    if (!res.ok) return;
    const reports = await res.json();
    if (!reports.length) { container.style.display = 'none'; return; }
    container.style.display = 'block';
    list.innerHTML = reports.map(r =>
      `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border)">
        <span>${r.title || r.report_type} <span class="dim">(#${r.report_id})</span></span>
        <span class="dim">${r.created_at ? r.created_at.slice(0, 16).replace('T', ' ') : ''}</span>
      </div>`
    ).join('');
  } catch (e) { /* ignore */ }
}



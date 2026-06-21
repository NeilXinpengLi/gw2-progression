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
  const signal = _abortController.signal;
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
}

// ── Value Dashboard ──
function renderValue(vd) {
  // Clean up old charts
  Object.values(_valueCharts).forEach(c => { try { c.destroy(); } catch(e) {} });
  _valueCharts = { _rendered: false };
  _valueCharts._rendered = false;

  const errEl = document.getElementById('err-value');
  if (!vd) {
    errEl.innerHTML = '<div class="error-box">Value analysis unavailable. Ensure your API key has the appropriate permissions (inventories, tradingpost).</div>';
    document.getElementById('value-summary-cards').innerHTML = '';
    document.getElementById('value-top-table').querySelector('tbody').innerHTML = '<tr><td colspan="7" class="dim">No value data</td></tr>';
    document.getElementById('value-warnings').innerHTML = '';
    return;
  }

  errEl.innerHTML = '';

  const s = vd.summary;

  const hist = vd.history || [];
  const prev = hist.length > 1 ? hist[1] : null;
  function vsPrev(current, prevVal) {
    if (prevVal === undefined || prevVal === null) return '';
    const diff = current - prevVal;
    if (diff === 0) return '';
    const cls = diff > 0 ? 'vs-up' : 'vs-down';
    const arrow = diff > 0 ? '▲' : '▼';
    return `<span class="${cls}">${arrow} ${fmtCoinShort(Math.abs(diff))}</span>`;
  }

  document.getElementById('value-summary-cards').innerHTML = `
    <div class="stat-card">
      <div class="label">Total Estimated Value</div>
      <div class="value">${fmtCoin(s.total_value_buy)}</div>
      <div class="sub">based on highest buy orders ${vsPrev(s.total_value_buy, prev?.total_value_buy)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Wallet Gold</div>
      <div class="value">${fmtCoin(s.wallet_value)}</div>
      <div class="sub">liquid gold ${vsPrev(s.wallet_value, prev?.wallet_value)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Reliable Value</div>
      <div class="value" style="color:#6bc46b">${fmtCoinShort(s.reliable_value)}</div>
      <div class="sub">high liquidity & fair spread</div>
    </div>
    <div class="stat-card">
      <div class="label">Risky Value</div>
      <div class="value" style="color:#d0a050">${fmtCoinShort(s.risky_value)}</div>
      <div class="sub">low liquidity or wide spread</div>
    </div>
    </div>
    <div class="stat-card">
      <div class="label">Materials (Buy)</div>
      <div class="value">${fmtCoinShort(s.material_value_buy)}</div>
      <div class="sub">material storage value ${vsPrev(s.material_value_buy, prev?.material_value)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Bank (Buy)</div>
      <div class="value">${fmtCoinShort(s.bank_value_buy)}</div>
      <div class="sub">bank inventory value ${vsPrev(s.bank_value_buy, prev?.bank_value)}</div>
    </div>
    <div class="stat-card">
      <div class="label">Characters (Buy)</div>
      <div class="value">${fmtCoinShort(s.character_inventory_value_buy)}</div>
      <div class="sub">character inventory value ${vsPrev(s.character_inventory_value_buy, prev?.inventory_value)}</div>
    </div>
    <div class="stat-card">
      <div class="label">TP Orders</div>
      <div class="value">${fmtCoinShort(s.tradingpost_value)}</div>
      <div class="sub">buy ${fmtCoinShort(s.tradingpost_buy_value)} | sell ${fmtCoinShort(s.tradingpost_sell_value)} ${vsPrev(s.tradingpost_value, prev?.tradingpost_value)}</div>
    </div>
  `.trim();

  // Valuation metric row
  document.getElementById('vc-instant').textContent = fmtCoin(s.total_value_buy);
  document.getElementById('vc-listing').textContent = fmtCoin(s.total_value_sell);
  document.getElementById('vc-net').textContent = fmtCoin(s.net_sell_value);

  // Stats row
  document.getElementById('vs-priced').textContent = s.priced_item_count?.toLocaleString() || '0';
  document.getElementById('vs-unpriced').textContent = s.unpriced_item_count?.toLocaleString() || '0';
  document.getElementById('vs-bound').textContent = s.account_bound_count?.toLocaleString() || '0';
  document.getElementById('vs-time').textContent = s.snapshot_time ? s.snapshot_time.slice(0, 16).replace('T', ' ') : '—';

  // Top items
  const tbody = document.querySelector('#value-top-table tbody');
  const items = vd.top_items || [];
  if (items.length) {
    tbody.innerHTML = items.map((item, i) => {
      const name = itemName(item.item_id);
      const icon = itemIcon(item.item_id);
      const img = icon ? `<img src="${icon}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">` : '';
      const locLabels = {
        material_storage: 'Material Storage',
        bank: 'Bank',
        character: 'Character',
        shared_inventory: 'Shared Inv',
        tradingpost: 'TP Orders',
        wallet: 'Wallet',
      };
      const loc = locLabels[item.location_type] || item.location_type;
      let statusEl = `<span class="perm-badge granted">Priced</span>`;
      if (item.valuation_status === 'unpriced') statusEl = `<span class="perm-badge missing">Unpriced</span>`;
      if (item.valuation_status === 'account_bound') statusEl = `<span class="perm-badge missing">Bound</span>`;
      const qualityMap = { reliable: '', low_liquidity: '⚠️', illiquid: '⚠️', wide_spread: '📊', missing_buy: '❓' };
      const qualityIcon = item.quality_status ? qualityMap[item.quality_status] || '' : '';
      return `<tr>
        <td>${i + 1}</td>
        <td>${img}<span class="gold-val">${name}</span> ${qualityIcon}</td>
        <td class="dim">${loc}${item.location_ref ? ' (' + item.location_ref.slice(0, 20) + ')' : ''}</td>
        <td>${item.count.toLocaleString()}</td>
        <td class="gold-val">${fmtCoinShort(item.value_buy)}</td>
        <td class="gold-val">${fmtCoinShort(item.value_sell)}</td>
        <td>${statusEl}</td>
      </tr>`;
    }).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="7" class="dim">No items with value data</td></tr>';
  }

  // Materials by Category (only from material_storage)
  const matHoldings = (vd.holdings || []).filter(h => h.location_type === 'material_storage');
  const matByCat = {};
  for (const h of matHoldings) {
    const cat = h.location_ref || '0';
    if (!matByCat[cat]) matByCat[cat] = { items: [], total_buy: 0, total_sell: 0 };
    matByCat[cat].items.push(h);
    matByCat[cat].total_buy += h.value_buy;
    matByCat[cat].total_sell += h.value_sell;
  }
  window._matByCat = matByCat;
  // Resolve mat categories
  const matCatIds = Object.keys(matByCat).filter(c => c !== '0').map(Number);
  if (matCatIds.length) resolveMatCategories();
  renderMaterialsGrid(matByCat);

  // All Holdings with pagination
  window._allHoldings = vd.holdings || [];
  window._holdingsPage = 0;
  window._holdingsPageSize = 50;
  document.getElementById('holdings-count').textContent = _allHoldings.length.toLocaleString();
  renderHoldingsPage();
  document.getElementById('holdings-count-display').textContent = `${_allHoldings.length} items total`;

  // Warnings
  const warningsEl = document.getElementById('value-warnings');
  const warnings = vd.warnings || [];
  if (warnings.length) {
    warningsEl.innerHTML = warnings.map(w => {
      const typeLabels = {
        missing_permissions: '⚠️',
        account_bound: '🔒',
        unpriced: '❓',
        no_price: '❓',
      };
      const icon = typeLabels[w.warning_type] || 'ℹ';
      return `<div class="error-box" style="margin-top:4px;padding:8px 12px;font-size:13px">
        <strong>${icon} ${w.warning_type}</strong>: ${w.message}${w.item_id ? ` (Item #${w.item_id})` : ''}
      </div>`;
    }).join('');
  } else {
    warningsEl.innerHTML = '<div class="dim" style="padding:8px 0">No valuation warnings.</div>';
  }

  // History visibility
  const hist = vd.history || [];
  const histContainer = document.getElementById('history-chart-container');
  const histEmpty = document.getElementById('value-history-empty');
  if (hist.length > 1) {
    histContainer.style.display = 'block';
    histEmpty.style.display = 'none';
  } else if (hist.length === 1) {
    histContainer.style.display = 'none';
    histEmpty.textContent = 'Only one snapshot recorded. Run valuation again to build history.';
    histEmpty.style.display = 'block';
  } else {
    histContainer.style.display = 'none';
    histEmpty.style.display = 'block';
  }

  // Destroy old chart instances
  ['value-pie-chart', 'value-bar-chart', 'value-line-chart'].forEach(id => {
    const canvas = document.getElementById(id);
    if (canvas) {
      const existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    }
  });

  _valueCharts._rendered = false;

  // Render charts if value tab is already active
  const valueTabBtn = document.querySelector('button[data-tab="value"]');
  if (valueTabBtn && valueTabBtn.classList.contains('active')) {
    renderValueCharts(vd);
  }
}

function renderValueCharts(vd) {
  if (!vd) return;
  _valueCharts._rendered = true;

  const darkBg = '#1a1a1a';
  const darkGrid = '#333';
  const textColor = '#888';

  // Colors for the pie/bar charts
  const COLORS = ['#c8956c', '#5a9e5a', '#5080a0', '#a05050', '#b080d0', '#d0b050'];
  const COLORS_ALPHA = ['rgba(200,149,108,0.8)', 'rgba(90,158,90,0.8)', 'rgba(80,128,160,0.8)',
                        'rgba(160,80,80,0.8)', 'rgba(176,128,208,0.8)', 'rgba(208,176,80,0.8)'];

  // 1. Pie chart: asset composition
  const breakdown = vd.breakdown?.by_location || [];
  const pieCanvas = document.getElementById('value-pie-chart');
  if (pieCanvas && breakdown.length) {
    const pieData = breakdown.filter(b => b.value_buy > 0);
    new Chart(pieCanvas, {
      type: 'doughnut',
      data: {
        labels: pieData.map(b => b.label),
        datasets: [{
          data: pieData.map(b => b.value_buy),
          backgroundColor: COLORS.slice(0, pieData.length),
          borderColor: '#0f0f0f',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            position: 'right',
            labels: {
              color: textColor,
              padding: 12,
              font: { size: 11 },
              generateLabels: function(chart) {
                const data = chart.data;
                return data.labels.map((label, i) => ({
                  text: `${label}: ${fmtCoinShort(data.datasets[0].data[i])}`,
                  fillStyle: data.datasets[0].backgroundColor[i],
                  strokeStyle: '#333',
                  index: i,
                }));
              },
            },
          },
          tooltip: {
            backgroundColor: '#111',
            borderColor: '#333',
            borderWidth: 1,
            titleColor: '#eee',
            bodyColor: '#ccc',
            callbacks: {
              label: ctx => ` ${ctx.label}: ${fmtCoin(ctx.parsed)}`,
            },
          },
        },
      },
    });
  }

  // 2. Bar chart: value by location
  const barCanvas = document.getElementById('value-bar-chart');
  if (barCanvas && breakdown.length) {
    const sorted = [...breakdown].sort((a, b) => b.value_buy - a.value_buy);
    new Chart(barCanvas, {
      type: 'bar',
      data: {
        labels: sorted.map(b => b.label),
        datasets: [
          {
            label: 'Buy Value',
            data: sorted.map(b => b.value_buy),
            backgroundColor: COLORS_ALPHA,
            borderColor: COLORS,
            borderWidth: 1,
            borderRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#111',
            borderColor: '#333',
            borderWidth: 1,
            titleColor: '#eee',
            bodyColor: '#ccc',
            callbacks: {
              label: ctx => ` ${fmtCoin(ctx.parsed.x)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: textColor,
              font: { size: 10 },
              callback: v => fmtCoinShort(v),
            },
            grid: { color: darkGrid },
          },
          y: {
            ticks: { color: textColor, font: { size: 11 } },
            grid: { display: false },
          },
        },
      },
    });
  }

  // 3. Line chart: value history
  const lineCanvas = document.getElementById('value-line-chart');
  const hist = vd.history || [];
  if (lineCanvas && hist.length > 1) {
    const sortedHist = [...hist].reverse();
    new Chart(lineCanvas, {
      type: 'line',
      data: {
        labels: sortedHist.map(h => h.snapshot_time ? h.snapshot_time.slice(5, 16).replace('T', ' ') : ''),
        datasets: [
          {
            label: 'Total Value (Buy)',
            data: sortedHist.map(h => h.total_value_buy),
            borderColor: '#c8956c',
            backgroundColor: 'rgba(200,149,108,0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: 'Total Value (Sell)',
            data: sortedHist.map(h => h.total_value_sell),
            borderColor: '#5a9e5a',
            backgroundColor: 'rgba(90,158,90,0.05)',
            fill: false,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
            borderDash: [4, 4],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: {
          intersect: false,
          mode: 'index',
        },
        plugins: {
          legend: {
            position: 'top',
            labels: { color: textColor, font: { size: 11 }, padding: 16 },
          },
          tooltip: {
            backgroundColor: '#111',
            borderColor: '#333',
            borderWidth: 1,
            titleColor: '#eee',
            bodyColor: '#ccc',
            callbacks: {
              label: ctx => ` ${ctx.dataset.label}: ${fmtCoin(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: textColor, font: { size: 10 }, maxTicksLimit: 10 },
            grid: { color: darkGrid },
          },
          y: {
            ticks: {
              color: textColor,
              font: { size: 10 },
              callback: v => fmtCoinShort(v),
            },
            grid: { color: darkGrid },
          },
        },
      },
    });
  }
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
// ── Items Tab ──
document.getElementById('items-search-btn').addEventListener('click', runItemsSearch);
document.getElementById('items-search-input').addEventListener('keydown', e => { if (e.key === 'Enter') runItemsSearch(); });
document.getElementById('items-detail-back').addEventListener('click', () => {
  document.getElementById('items-detail').classList.add('hidden');
  document.getElementById('items-results-table').classList.remove('hidden');
});

document.querySelectorAll('.quick-filter-btn').forEach(btn => {
  btn.addEventListener('click', () => runItemsFilter(btn.dataset.filter));
});

let _itemsSearchTimer = null;
document.getElementById('items-search-input').addEventListener('input', () => {
  clearTimeout(_itemsSearchTimer);
  _itemsSearchTimer = setTimeout(() => {
    if (document.getElementById('items-search-input').value.trim().length >= 2) runItemsSearch();
  }, 400);
});

async function runItemsSearch() {
  const q = document.getElementById('items-search-input').value.trim();
  const loc = document.getElementById('items-location-filter').value;
  const status = document.getElementById('items-status-filter').value;
  const accountName = _accountData?.account_name;
  if (!accountName) { setItemsStatus('error', 'Run analysis first (Overview tab).'); return; }
  if (!q) { setItemsStatus('error', 'Enter an item name or ID.'); return; }

  setItemsStatus('', '<span class="spinner"></span> Searching…');
  await _doItemsFetch(`/value/items/search?account_name=${encodeURIComponent(accountName)}&q=${encodeURIComponent(q)}${loc ? '&location='+loc : ''}${status ? '&status='+status : ''}`);
}

async function runItemsFilter(filter) {
  const accountName = _accountData?.account_name;
  if (!accountName) { setItemsStatus('error', 'Run analysis first.'); return; }
  setItemsStatus('', `<span class="spinner"></span> Loading ${filter} items…`);
  await _doItemsFetch(`/value/items/${filter}?account_name=${encodeURIComponent(accountName)}`);
}

async function _doItemsFetch(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data) ? data : [];

    // Resolve item names
    const ids = [...new Set(items.map(i => i.item_id).filter(Boolean))];
    if (ids.length) await resolveItems(ids);

    document.getElementById('items-results').classList.remove('hidden');
    document.getElementById('items-detail').classList.add('hidden');
    document.getElementById('items-results-table').classList.remove('hidden');

    const tbody = document.querySelector('#items-results-table tbody');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="dim">No items found.</td></tr>';
      document.getElementById('items-results-title').textContent = 'Results (0)';
    } else {
      document.getElementById('items-results-title').textContent = `Results (${items.length})`;
      tbody.innerHTML = items.map((h, i) => {
        const name = itemName(h.item_id);
        const icon = itemIcon(h.item_id);
        const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
        const locLabels = { material_storage: 'Material Storage', bank: 'Bank', character: 'Character', shared_inventory: 'Shared', tradingpost: 'TP', wallet: 'Wallet' };
        let loc = locLabels[h.location_type] || h.location_type;
        if (h.location_type === 'character' && h.location_ref) loc = 'Char: ' + h.location_ref.split('/')[0];
        let statusEl = `<span class="perm-badge granted">Priced</span>`;
        if (h.valuation_status === 'unpriced') statusEl = `<span class="perm-badge missing">Unpriced</span>`;
        if (h.valuation_status === 'account_bound') statusEl = `<span class="perm-badge missing">Bound</span>`;
        return `<tr style="cursor:pointer" data-item-id="${h.item_id}">
          <td>${img}<span class="gold-val">${name}</span></td>
          <td>${h.count.toLocaleString()}</td>
          <td class="dim">${loc}</td>
          <td class="gold-val">${h.value_buy ? fmtCoinShort(h.value_buy) : '—'}</td>
          <td class="gold-val">${h.value_sell ? fmtCoinShort(h.value_sell) : '—'}</td>
          <td>${statusEl}</td>
        </tr>`;
      }).join('');
    }

    // Click to show item detail
    tbody.querySelectorAll('tr[data-item-id]').forEach(row => {
      row.addEventListener('click', () => loadItemDetail(parseInt(row.dataset.itemId)));
    });

    setItemsStatus('ok', `Found ${items.length} result(s).`);
  } catch (e) {
    setItemsStatus('error', `Error: ${e.message}`);
  }
}

async function loadItemDetail(itemId) {
  const accountName = _accountData?.account_name;
  if (!accountName) return;

  document.getElementById('items-detail').classList.remove('hidden');
  document.getElementById('items-results-table').classList.add('hidden');
  document.getElementById('items-detail-title').textContent = `Item #${itemId} Detail`;

  try {
    const [detailRes, listingRes] = await Promise.all([
      fetch(`/value/items/${itemId}/detail?account_name=${encodeURIComponent(accountName)}&item_id=${itemId}`),
      fetch(`/value/listings/${itemId}`),
    ]);
    const detail = await detailRes.json();
    const listing = listingRes.ok ? await listingRes.json() : null;
    await resolveItems([detail.item_id]);

    document.getElementById('items-detail-grid').innerHTML = `
      <div class="value-stat-box"><div class="vsl-label">Total Count</div><div class="vsl-value">${detail.total_count.toLocaleString()}</div></div>
      <div class="value-stat-box"><div class="vsl-label">Total Buy Value</div><div class="vsl-value gold-val">${fmtCoinShort(detail.total_value_buy)}</div></div>
      <div class="value-stat-box"><div class="vsl-label">Total Sell Value</div><div class="vsl-value gold-val">${fmtCoinShort(detail.total_value_sell)}</div></div>
      <div class="value-stat-box"><div class="vsl-label">Status</div><div class="vsl-value vsl-small">${detail.valuation_status}</div></div>
    `;

    // TP listing analysis
    const tpContainer = document.getElementById('items-detail-tp');
    if (listing && !listing.error) {
      const arb = listing.arbitrage_viable
        ? `<span class="perm-badge granted">✓ Arbitrage viable (${fmtCoinShort(listing.net_profit)} profit)</span>`
        : `<span class="perm-badge missing">No arbitrage</span>`;
      tpContainer.innerHTML = `<div class="section-title" style="margin-top:12px">Market Depth</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-bottom:12px">
          <div class="value-stat-box"><div class="vsl-label">Best Buy</div><div class="vsl-value gold-val">${fmtCoinShort(listing.best_buy)}</div><div class="vsl-small dim">qty: ${listing.best_buy_qty?.toLocaleString() || 0}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Best Sell</div><div class="vsl-value gold-val">${fmtCoinShort(listing.best_sell)}</div><div class="vsl-small dim">qty: ${listing.best_sell_qty?.toLocaleString() || 0}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Spread</div><div class="vsl-value">${fmtCoinShort(listing.spread)}</div><div class="vsl-small dim">ratio: ${(listing.spread_ratio * 100).toFixed(1)}%</div></div>
          <div class="value-stat-box"><div class="vsl-label">Buy Depth (top 5)</div><div class="vsl-value">${(listing.buy_depth_5 || 0).toLocaleString()}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Sell Depth (top 5)</div><div class="vsl-value">${(listing.sell_depth_5 || 0).toLocaleString()}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Profit Margin</div><div class="vsl-value ${listing.net_profit > 0 ? 'vs-up' : 'vs-down'}">${listing.profit_margin?.toFixed(1) || 0}%</div></div>
        </div>
        <div style="margin-bottom:12px">${arb}</div>`;
    } else {
      tpContainer.innerHTML = '';
    }

    const locs = document.getElementById('items-detail-locations');
    const entries = Object.entries(detail.locations || {});
    if (!entries.length) {
      locs.innerHTML = '<div class="dim">No location data.</div>';
    } else {
      const locLabels = { material_storage: 'Material Storage', bank: 'Bank', character: 'Character', shared_inventory: 'Shared Inventory', tradingpost: 'Trading Post', wallet: 'Wallet' };
      locs.innerHTML = entries.map(([locType, locItems]) => `
        <div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px">
          <div style="font-weight:600;color:var(--gold);margin-bottom:6px">${locLabels[locType] || locType} (${locItems.length} slot(s))</div>
          ${locItems.map(li => {
            let ref = li.location_ref || '';
            if (locType === 'character' && ref) ref = ' (' + ref.split('/')[0] + ')';
            return `<div style="display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px solid var(--border)">
              <span class="dim">${ref}</span>
              <span>×${li.count.toLocaleString()}</span>
              <span class="gold-val">${fmtCoinShort(li.value_buy)}</span>
              <span>${li.tradable ? '<span class="perm-badge granted">Tradable</span>' : '<span class="perm-badge missing">Bound</span>'}</span>
            </div>`;
          }).join('')}
        </div>
      `).join('');
    }
  } catch (e) {
    document.getElementById('items-detail-grid').innerHTML = `<div class="dim">Failed: ${e.message}</div>`;
  }
}

function setItemsStatus(cls, msg) {
  const el = document.getElementById('items-status');
  el.className = cls === 'error' ? 'error' : '';
  el.innerHTML = msg;
}

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

// ── Crafting Calculator ──
document.getElementById('craft-btn').addEventListener('click', runCrafting);
document.getElementById('craft-target').addEventListener('keydown', e => { if (e.key === 'Enter') runCrafting(); });

let _craftSearchTimer = null;

document.getElementById('craft-search').addEventListener('input', () => {
  clearTimeout(_craftSearchTimer);
  const q = document.getElementById('craft-search').value.trim();
  if (q.length < 2) {
    document.getElementById('craft-search-results').classList.add('hidden');
    return;
  }
  _craftSearchTimer = setTimeout(() => doCraftSearch(q), 300);
});

document.addEventListener('click', e => {
  const dd = document.getElementById('craft-search-results');
  if (!e.target.closest('#craft-search') && !e.target.closest('.craft-search-dropdown')) {
    dd.classList.add('hidden');
  }
});

async function doCraftSearch(query) {
  const dd = document.getElementById('craft-search-results');
  try {
    const ids = await resolveSearch(query);
    if (!ids || !ids.length) {
      dd.innerHTML = '<div class="craft-search-item dim">No results</div>';
      dd.classList.remove('hidden');
      return;
    }
    // Resolve names for the first 20
    await resolveItems(ids.slice(0, 20));
    dd.innerHTML = ids.slice(0, 15).map(id => {
      const name = itemName(id);
      const icon = itemIcon(id);
      const img = icon ? `<img src="${icon}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">` : '';
      return `<div class="craft-search-item" data-id="${id}">${img}${name} <span class="dim">(#${id})</span></div>`;
    }).join('');
    dd.classList.remove('hidden');
    dd.querySelectorAll('.craft-search-item').forEach(el => {
      el.addEventListener('click', () => {
        document.getElementById('craft-target').value = el.dataset.id;
        document.getElementById('craft-search').value = el.textContent.trim().split(' (#')[0];
        dd.classList.add('hidden');
      });
    });
  } catch (e) {
    dd.innerHTML = '<div class="craft-search-item dim">Search failed</div>';
    dd.classList.remove('hidden');
  }
}

async function runCrafting() {
  const target = parseInt(document.getElementById('craft-target').value);
  const qty = parseInt(document.getElementById('craft-qty').value) || 1;
  const useOwned = document.getElementById('craft-use-owned').checked;
  const key = document.getElementById('key-input').value.trim();

  if (!key) {
    setCraftStatus('error', 'Please enter an API key first.');
    return;
  }
  if (!target || target < 1) {
    setCraftStatus('error', 'Please enter a valid target item ID.');
    return;
  }

  const btn = document.getElementById('craft-btn');
  btn.disabled = true;
  setCraftStatus('', '<span class="spinner"></span> Fetching account data…');

  // Resolve target name while calculating
  resolveItems([target]);

  setCraftStatus('', '<span class="spinner"></span> Fetching recipe tree & prices…');
  document.getElementById('craft-results').classList.add('hidden');

  try {
    const res = await fetch('/crafting/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key, target_item_id: target, quantity: qty, use_owned: useOwned }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();

    // Resolve ALL item IDs from the crafting response
    const allIds = new Set([target]);
    for (const item of (data.missing_items || [])) { if (item.item_id) allIds.add(item.item_id); }
    for (const item of (data.shopping_list || [])) { if (item.item_id) allIds.add(item.item_id); }
    for (const step of (data.crafting_steps || [])) { if (step.item_id) allIds.add(step.item_id); }
    setCraftStatus('', '<span class="spinner"></span> Resolving item names…');
    await resolveItems([...allIds]);

    // Resolve names for alternative recipe ingredients too
    for (const alt of (data.alternative_recipes || [])) {
      for (const ing of (alt.ingredients || [])) {
        if (ing.item_id) allIds.add(ing.item_id);
      }
    }
    setCraftStatus('ok', 'Calculation complete.');
    renderCraftingResults(data);
  } catch (e) {
    setCraftStatus('error', `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
}

function setCraftStatus(cls, msg) {
  const el = document.getElementById('craft-status');
  el.className = cls === 'error' ? 'error' : (cls === 'ok' ? '' : '');
  el.innerHTML = msg;
}

function renderCraftingResults(data) {
  const container = document.getElementById('craft-results');
  container.classList.remove('hidden');

  const targetName = itemName(data.target_item_id) || `Item #${data.target_item_id}`;
  document.getElementById('craft-target-name').textContent =
    `${targetName} × ${data.target_count}`;

  document.getElementById('craft-buy-cost').textContent = fmtCoin(data.total_buy_cost);
  document.getElementById('craft-craft-cost').textContent = fmtCoin(data.total_craft_cost);
  document.getElementById('craft-owned-used').textContent = fmtCoin(data.owned_used * 10000) || '0g';

  // Shopping list
  const shopping = document.getElementById('craft-shopping');
  const sl = data.shopping_list || [];
  if (sl.length) {
    shopping.innerHTML = '<table class="data-table"><thead><tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead><tbody>' +
      sl.map(item => {
        const icon = itemIcon(item.item_id);
        const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
        return `<tr>
          <td>${img}${itemName(item.item_id)}</td>
          <td>${item.count.toLocaleString()}</td>
          <td class="gold-val">${fmtCoinShort(item.unit_price)}</td>
          <td class="gold-val">${fmtCoinShort(item.total)}</td>
        </tr>`;
      }).join('') + '</tbody></table>';
  } else {
    shopping.innerHTML = '<div class="dim">Nothing to buy — all materials are owned!</div>';
  }

  // Crafting steps
  const steps = document.getElementById('craft-steps');
  const cs = data.crafting_steps || [];
  if (cs.length) {
    steps.innerHTML = '<div style="display:flex;flex-direction:column;gap:4px">' +
      cs.map(s => {
        const indent = s.depth * 16;
        const icon = itemIcon(s.item_id);
        const img = icon ? `<img src="${icon}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">` : '';
        return `<div style="margin-left:${indent}px;padding:6px 10px;background:var(--bg2);border:1px solid var(--border);border-radius:3px;display:flex;align-items:center;gap:8px">
          ${img}
          <span style="flex:1">${itemName(s.item_id)} × ${s.count.toLocaleString()}</span>
          <span class="${s.missing > 0 ? 'gold-val' : 'dim'}">Owned: ${s.owned} | Missing: ${s.missing}</span>
          <span class="gold-val">${fmtCoinShort(s.buy_cost)}</span>
        </div>`;
      }).join('') + '</div>';
  } else {
    steps.innerHTML = '<div class="dim">No crafting steps needed (item has no recipe or all materials owned at base level).</div>';
  }

  // Missing materials detail
  const missing = document.getElementById('craft-missing-detail');
  const mi = data.missing_items || [];
  if (mi.length) {
    missing.innerHTML = '<table class="data-table"><thead><tr><th>Item</th><th>Needed</th><th>Owned</th><th>Missing</th><th>Unit Price</th><th>Total Cost</th></tr></thead><tbody>' +
      mi.map(item => {
        const icon = itemIcon(item.item_id);
        const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
        return `<tr>
          <td>${img}${itemName(item.item_id)}</td>
          <td>${item.needed.toLocaleString()}</td>
          <td>${item.owned.toLocaleString()}</td>
          <td class="gold-val">${item.missing.toLocaleString()}</td>
          <td>${fmtCoinShort(item.buy_unit_price)}</td>
          <td class="gold-val">${fmtCoinShort(item.total_cost)}</td>
        </tr>`;
      }).join('') + '</tbody></table>';
  } else {
    missing.innerHTML = '<div class="dim">No missing materials.</div>';
  }

  // Alternative recipes
  const altContainer = document.getElementById('craft-alternatives');
  const alts = data.alternative_recipes || [];
  if (alts.length) {
    altContainer.innerHTML = '<div style="display:flex;flex-direction:column;gap:8px">' +
      alts.map(alt => {
        const ings = (alt.ingredients || []).map(ing => {
          const icon = itemIcon(ing.item_id);
          const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:3px;border-radius:2px">` : '';
          return `${img}${itemName(ing.item_id)} ×${ing.count}`;
        }).join(', ');
        return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:10px 14px;font-size:13px">
          <span style="color:var(--gold)">Recipe #${alt.recipe_id}</span>
          <span class="dim"> — ${(alt.disciplines || []).join(', ')} (Rating ${alt.min_rating})</span>
          <div style="margin-top:4px;color:var(--text-dim)">${ings}</div>
        </div>`;
      }).join('') + '</div>';
  } else {
    altContainer.innerHTML = '<div class="dim">No alternative recipes found.</div>';
  }
}

function toggleHoldings() {
  const section = document.getElementById('holdings-section');
  const title = section.previousElementSibling;
  const isHidden = section.style.display === 'none';
  section.style.display = isHidden ? 'block' : 'none';
  if (title) {
    const span = title.querySelector('span');
    if (span) span.innerHTML = (isHidden ? '▼' : '▶') + span.innerHTML.slice(1);
  }
}

function renderMaterialsGrid(matByCat) {
  const grid = document.getElementById('materials-grid');
  const entries = Object.entries(matByCat).sort((a, b) => b[1].total_buy - a[1].total_buy);
  if (!entries.length) {
    grid.innerHTML = '<div class="dim">No material storage data.</div>';
    return;
  }
  grid.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px">' +
    entries.map(([cat, data]) => {
      const catName = _matCatCache[cat] || `Category ${cat}`;
      const top = [...data.items].sort((a, b) => b.value_buy - a.value_buy).slice(0, 5);
      const topItems = top.map(h => {
        const icon = itemIcon(h.item_id);
        const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:3px;border-radius:2px">` : '';
        return `<div style="font-size:11px;color:var(--text-dim);display:flex;align-items:center;gap:4px">
          ${img}<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${itemName(h.item_id)}</span>
          <span class="gold-val">${fmtCoinShort(h.value_buy)}</span>
        </div>`;
      }).join('');
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px">
        <div style="font-size:12px;color:var(--gold);font-weight:600;margin-bottom:6px">${catName}</div>
        <div style="font-size:18px;font-weight:600;color:var(--gold-light);margin-bottom:6px">${fmtCoinShort(data.total_buy)}</div>
        <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">${data.items.length} items</div>
        ${topItems}
      </div>`;
    }).join('') + '</div>';
}

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

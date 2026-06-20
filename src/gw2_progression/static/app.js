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

async function runAnalyze() {
  const key = document.getElementById('key-input').value.trim();
  if (!key) {
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
  msg.innerHTML = '<span class="spinner"></span> Fetching account data…';

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
        body: JSON.stringify({ api_key: key }),
        signal,
      }),
      fetch('/value/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key }),
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
      return `<tr>
        <td>${i + 1}</td>
        <td>${img}<span class="gold-val">${name}</span></td>
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

// ── Characters ──
const DOLL_ARMOR = [
  { slot: 'Helm',       col: 0, row: 0, label: 'Helm' },
  { slot: 'Shoulders',  col: 1, row: 0, label: 'Shoulders' },
  { slot: 'Coat',       col: 0, row: 1, label: 'Coat' },
  { slot: 'Gloves',     col: 1, row: 1, label: 'Gloves' },
  { slot: 'Leggings',   col: 0, row: 2, label: 'Leggings' },
  { slot: 'Boots',      col: 1, row: 2, label: 'Boots' },
  { slot: 'Backpack',   col: 0, row: 3, label: 'Back' },
  { slot: 'Amulet',     col: 1, row: 3, label: 'Amulet' },
  { slot: 'Accessory1', col: 0, row: 4, label: 'Acc 1' },
  { slot: 'Accessory2', col: 1, row: 4, label: 'Acc 2' },
  { slot: 'Ring1',      col: 0, row: 5, label: 'Ring 1' },
  { slot: 'Ring2',      col: 1, row: 5, label: 'Ring 2' },
];
const DOLL_WEAPONS = [
  { slot: 'WeaponA1', label: 'Main 1' },
  { slot: 'WeaponA2', label: 'Off 1' },
  { slot: 'WeaponB1', label: 'Main 2' },
  { slot: 'WeaponB2', label: 'Off 2' },
];

let _chars = [];

function renderCharacters(chars) {
  _chars = chars;
  const sel = document.getElementById('char-selector');
  sel.innerHTML = chars.map((c, i) => `
    <button class="char-btn${i === 0 ? ' active' : ''}" data-idx="${i}">
      ${c.name}
    </button>`).join('');
  sel.addEventListener('click', e => {
    const btn = e.target.closest('.char-btn');
    if (!btn) return;
    document.querySelectorAll('.char-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    showCharacter(parseInt(btn.dataset.idx));
  });
  if (chars.length) showCharacter(0);
}

function showCharacter(idx) {
  const ch = _chars[idx];
  if (!ch) return;
  const eqMap = {};
  for (const eq of (ch.equipment || [])) eqMap[eq.slot] = eq;

  const dollSlots = DOLL_ARMOR.map(s => renderDollSlot(s.slot, s.label, eqMap[s.slot])).join('');
  const weaponSlots = DOLL_WEAPONS.map(s => renderDollSlot(s.slot, s.label, eqMap[s.slot])).join('');

  const equipRows = [...DOLL_ARMOR, ...DOLL_WEAPONS].map(s => {
    const eq = eqMap[s.slot];
    if (!eq) return '';
    const skinId = eq.skin || eq.id;
    const icon = skinIcon(skinId) || itemIcon(eq.id);
    const name = skinName(skinId) !== `Skin #${skinId}` ? skinName(skinId) : itemName(eq.id);
    const dyes = (eq.dyes || []).filter(d => d != null).map(d =>
      `<span class="dye-dot" style="background:${colorHex(d)}" title="${_colorCache[d]?.name || ''}"></span>`).join('');
    return `<div class="equip-row">
      ${icon ? `<img src="${icon}" alt="">` : '<div style="width:32px;height:32px;background:#333;border-radius:2px"></div>'}
      <span class="eq-slot">${s.label}</span>
      <span class="eq-name">${name}</span>
      <span class="eq-dyes">${dyes}</span>
    </div>`;
  }).filter(Boolean).join('');

  document.getElementById('char-detail').innerHTML = `
    <div class="char-viewer">
      <div>
        <div class="paper-doll">${dollSlots}</div>
        <div class="doll-weapons">${weaponSlots}</div>
      </div>
      <div class="char-info">
        <div class="char-info-header">
          <div class="char-name">${ch.name}</div>
          <div class="char-meta">${ch.race} · ${ch.profession} · Level ${ch.level} · ${ch.gender}</div>
          ${ch.guild ? (() => { const g = _guildCache[ch.guild] || {}; return `<div style="margin-top:5px"><span style="background:#1e2a1e;border:1px solid #3a5a3a;border-radius:3px;padding:3px 8px;font-size:12px;color:#6bc46b">[${g.tag || '?'}] ${g.name || ch.guild}</span></div>`; })() : ''}
        </div>
        <div class="char-stats-grid">
          <div class="char-stat-box"><div class="cs-label">Playtime</div><div class="cs-val">${Math.round((ch.age||0)/3600)}h</div></div>
          <div class="char-stat-box"><div class="cs-label">Deaths</div><div class="cs-val">${ch.deaths ?? 0}</div></div>
          <div class="char-stat-box"><div class="cs-label">Created</div><div class="cs-val">${(ch.created||'').slice(0,10)}</div></div>
          <div class="char-stat-box"><div class="cs-label">Equipment</div><div class="cs-val">${(ch.equipment||[]).length}</div></div>
          <div class="char-stat-box"><div class="cs-label">Crafting</div><div class="cs-val">${(ch.crafting||[]).map(x=>x.discipline).join(', ')||'—'}</div></div>
        </div>
        <div class="section-title" style="margin-top:0">Equipment</div>
        <div class="equip-list">${equipRows}</div>
      </div>
    </div>`;
}

function renderDollSlot(slot, label, eq) {
  if (!eq) {
    return `<div class="doll-slot">
      <span class="slot-empty">·</span>
      <span class="slot-label">${label}</span>
    </div>`;
  }
  const skinId = eq.skin || eq.id;
  const icon = skinIcon(skinId) || itemIcon(eq.id);
  const name = skinName(skinId) !== `Skin #${skinId}` ? skinName(skinId) : itemName(eq.id);
  const dyes = (eq.dyes || []).filter(d => d != null).map(d =>
    `<span class="dye-dot" style="background:${colorHex(d)}"></span>`).join('');
  return `<div class="doll-slot">
    <div class="tooltip">${name}</div>
    ${icon ? `<img src="${icon}" alt="${name}">` : `<span class="slot-empty">?</span>`}
    <span class="slot-label">${label}</span>
    ${dyes ? `<div class="dye-row">${dyes}</div>` : ''}
  </div>`;
}

// ── Wardrobe ──
let _allSkinIds = [];
let _wardrobeLoaded = false;
let _wardrobeFiltered = [];
let _wardrobeVisible = 200;
const WARDROBE_PAGE = 200;

function setupWardrobe(skinIds) {
  _allSkinIds = skinIds;
  _wardrobeLoaded = false;
  _wardrobeVisible = WARDROBE_PAGE;

  document.querySelectorAll('#nav-tabs button').forEach(btn => {
    if (btn.dataset.tab === 'wardrobe') {
      btn.addEventListener('click', loadWardrobeOnce, { once: false });
    }
  });

  let _wardrobeSearchTimer = null;

  document.getElementById('wardrobe-search').addEventListener('input', () => {
    clearTimeout(_wardrobeSearchTimer);
    _wardrobeSearchTimer = setTimeout(resetWardrobePagination, 200);
  });
  document.getElementById('wardrobe-type').addEventListener('change', () => {
    populateSubtypes();
    resetWardrobePagination();
  });
  document.getElementById('wardrobe-subtype').addEventListener('change', resetWardrobePagination);
}

function resetWardrobePagination() {
  _wardrobeVisible = WARDROBE_PAGE;
  filterWardrobe();
}

async function loadWardrobeOnce() {
  if (_wardrobeLoaded) return;
  _wardrobeLoaded = true;
  const loadingEl = document.getElementById('wardrobe-loading');
  loadingEl.classList.remove('hidden');

  await resolveSkins(_allSkinIds);
  loadingEl.classList.add('hidden');
  populateSubtypes();
  filterWardrobe();
}

function populateSubtypes() {
  const typeFilter = document.getElementById('wardrobe-type').value;
  const subtypes = new Set();
  for (const id of _allSkinIds) {
    const s = _skinCache[id];
    if (!s) continue;
    if (typeFilter && s.type !== typeFilter) continue;
    if (s.subtype) subtypes.add(s.subtype);
  }
  const sel = document.getElementById('wardrobe-subtype');
  const current = sel.value;
  sel.innerHTML = '<option value="">All subtypes</option>' +
    [...subtypes].sort().map(st => `<option value="${st}"${st === current ? ' selected' : ''}>${st}</option>`).join('');
}

function filterWardrobe() {
  const search    = document.getElementById('wardrobe-search').value.toLowerCase();
  const typeF     = document.getElementById('wardrobe-type').value;
  const subtypeF  = document.getElementById('wardrobe-subtype').value;

  _wardrobeFiltered = _allSkinIds.filter(id => {
    const s = _skinCache[id];
    if (!s) return false;
    if (typeF    && s.type    !== typeF)    return false;
    if (subtypeF && s.subtype !== subtypeF) return false;
    if (search   && !s.name.toLowerCase().includes(search)) return false;
    return true;
  });

  renderWardrobePage();
}

function showMoreWardrobe() {
  _wardrobeVisible += WARDROBE_PAGE;
  renderWardrobePage();
}

function renderWardrobePage() {
  const total = _wardrobeFiltered.length;
  const show = Math.min(_wardrobeVisible, total);

  document.getElementById('wardrobe-count').textContent =
    `Showing ${show.toLocaleString()} of ${total.toLocaleString()} skins`;

  const grid = document.getElementById('skin-grid');
  if (!total) {
    grid.innerHTML = '<div style="grid-column:1/-1;padding:30px 0;text-align:center;color:var(--text-dim)">No skins match your search criteria.</div>';
    return;
  }
  grid.innerHTML = _wardrobeFiltered.slice(0, show).map(id => {
    const s = _skinCache[id] || {};
    return `<div class="skin-card">
      ${s.icon ? `<img src="${s.icon}" alt="${s.name || ''}">` : '<div style="width:56px;height:56px;background:#333;border-radius:3px"></div>'}
      <div class="sk-name">${s.name || `#${id}`}</div>
      <div class="sk-type">${s.subtype || s.type || ''}</div>
    </div>`;
  }).join('');

  if (show < total) {
    const loadMore = document.createElement('div');
    loadMore.style.cssText = 'grid-column:1/-1;text-align:center;padding:16px 0';
    loadMore.innerHTML = `<button style="background:var(--gold);border:none;border-radius:3px;color:#111;cursor:pointer;font-size:13px;font-weight:600;padding:8px 20px" onclick="showMoreWardrobe()">
      Show ${Math.min(WARDROBE_PAGE, total - show).toLocaleString()} more (${(total - show).toLocaleString()} remaining)
    </button>`;
    grid.appendChild(loadMore);
  }
}

// ── Wallet ──
function renderWallet(wallet) {
  const sorted = [...wallet].sort((a, b) => b.value - a.value);
  document.getElementById('wallet-list').innerHTML = sorted.map(w => {
    const name = currencyName(w.id);
    const desc = _currencyCache[w.id]?.description || '';
    const qty  = w.id === 1 ? fmtCoin(w.value) : w.value.toLocaleString();
    return `<div class="currency-row">
      <div class="currency-name">${name}</div>
      <div class="currency-desc">${desc}</div>
      <div class="currency-qty">${qty}</div>
    </div>`;
  }).join('');
}

// ── Inventory ──
function renderInventory(d) {
  const mats = (d.materials || []).filter(m => m.count > 0).sort((a, b) => b.count - a.count).slice(0, 40);
  document.querySelector('#materials-table tbody').innerHTML = mats.map(m => {
    const icon = itemIcon(m.id);
    const img = icon ? `<img src="${icon}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">` : '';
    return `<tr>
      <td>${img}<span class="gold-val">${itemName(m.id)}</span></td>
      <td>${m.count.toLocaleString()}</td>
      <td class="dim">${matCatName(m.category)}</td>
    </tr>`;
  }).join('');

  const bank = d.bank || [];
  const used = bank.filter(s => s !== null).length;
  document.getElementById('bank-summary').innerHTML = `
    <div class="stat-card" style="display:inline-block;min-width:160px">
      <div class="label">Bank Slots</div>
      <div class="value">${used} / ${bank.length}</div>
      <div class="sub">slots occupied</div>
    </div>`;

  const shared = d.shared_inventory;
  const sharedList = document.getElementById('shared-inv-list');
  if (!shared) {
    sharedList.innerHTML = '<div class="dim">No shared inventory data</div>';
    return;
  }
  const slots = Array.isArray(shared) ? shared : [shared];
  const items = slots.filter(s => s !== null);
  if (!items.length) {
    sharedList.innerHTML = '<div class="dim">All shared inventory slots are empty</div>';
    return;
  }
  sharedList.innerHTML = `<div class="stat-card" style="display:inline-block;min-width:160px;margin-bottom:12px">
    <div class="label">Slots Used</div>
    <div class="value">${items.length} / ${slots.length}</div>
    <div class="sub">shared inventory slots</div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px">${items.map(s => {
    const icon = itemIcon(s.id);
    return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:8px;text-align:center;width:80px">
      ${icon ? `<img src="${icon}" width="40" height="40" style="border-radius:3px">` : '<div style="width:40px;height:40px;background:#333;border-radius:3px;margin:0 auto"></div>'}
      <div style="font-size:11px;color:var(--text-dim);margin-top:4px;word-break:break-all">${itemName(s.id)}</div>
      ${s.count > 1 ? `<div style="font-size:11px;color:var(--gold)">×${s.count}</div>` : ''}
    </div>`;
  }).join('')}</div>`;
}

// ── Progression ──
function renderProgression(d) {
  document.querySelector('#masteries-table tbody').innerHTML =
    (d.masteries || []).map(m => `
      <tr>
        <td class="gold-val">${masteryName(m.id)}</td>
        <td class="dim">${masteryRegion(m.id)}</td>
        <td>${m.level}</td>
      </tr>`).join('') || '<tr><td colspan="3" class="dim">No mastery data</td></tr>';

  const totals = (d.mastery_points?.totals || []);
  document.getElementById('mastery-point-cards').innerHTML = totals.map(t => `
    <div class="stat-card">
      <div class="label">${t.region}</div>
      <div class="value">${t.spent} / ${t.earned}</div>
      <div class="sub">spent / earned</div>
    </div>`).join('');

  document.getElementById('achiev-summary').innerHTML = `
    <div class="stat-card" style="display:inline-block;min-width:200px">
      <div class="label">Achievements</div>
      <div class="value">${(d.achievements || []).length.toLocaleString()}</div>
      <div class="sub">tracked on account</div>
    </div>`;
}

// ── PvP ──
function renderPvp(d) {
  const stats = d.pvp_stats || {};
  const agg   = stats.aggregate || {};
  const wins  = agg.wins?.pvp ?? 0;
  const losses= agg.losses?.pvp ?? 0;
  const total = wins + losses;
  document.getElementById('pvp-grid').innerHTML = [
    { label: 'PvP Rank',   value: stats.pvp_rank ?? '—' },
    { label: 'Wins',       value: wins },
    { label: 'Losses',     value: losses },
    { label: 'Win Rate',   value: total ? `${Math.round(wins/total*100)}%` : '—' },
    { label: 'Desertions', value: agg.desertions?.pvp ?? 0 },
    { label: 'Byes',       value: agg.byes?.pvp ?? 0 },
  ].map(s => `<div class="pvp-stat"><div class="ps-label">${s.label}</div><div class="ps-val">${s.value}</div></div>`).join('');

  document.querySelector('#pvp-games-table tbody').innerHTML =
    (d.pvp_games || []).map(g => `
      <tr>
        <td>${mapName(g.map_id)}</td>
        <td class="${g.result === 'Victory' ? 'gold-val' : 'dim'}">${g.result ?? '—'}</td>
        <td>${g.scores?.red ?? g.scores?.blue ?? '—'}</td>
        <td>${g.profession ?? '—'}</td>
      </tr>`).join('') || '<tr><td colspan="4" class="dim">No recent games</td></tr>';

  const standings = d.pvp_standings || [];
  document.getElementById('pvp-standings-list').innerHTML = standings.length
    ? `<table class="data-table"><thead><tr><th>#</th><th>Team/Division</th><th>Rating</th><th>Wins</th><th>Losses</th></tr></thead><tbody>${standings.map((s, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${s.division_name ?? s.ladder_name ?? '—'}</td>
        <td class="gold-val">${s.rating?.toLocaleString() ?? '—'}</td>
        <td>${s.wins ?? '—'}</td>
        <td>${s.losses ?? '—'}</td>
      </tr>`).join('')}</tbody></table>`
    : '<div class="dim">No ladder standings data</div>';
}

// ── Unlocks ──
function renderUnlocks(d) {
  document.getElementById('unlock-grid').innerHTML = [
    { label: 'Skins',     val: d.unlocked_skins_count },
    { label: 'Dyes',      val: d.unlocked_dyes_count },
    { label: 'Minis',     val: d.unlocked_minis_count },
    { label: 'Finishers', val: (d.unlocked_finishers || []).length },
  ].map(u => `<div class="unlock-card"><div class="u-label">${u.label}</div><div class="u-val">${u.val ?? '—'}</div></div>`).join('');

  document.querySelector('#finishers-table tbody').innerHTML =
    (d.unlocked_finishers || []).map(f => `
      <tr>
        <td class="gold-val">Finisher #${f.id}</td>
        <td>${f.permanent ? 'Yes' : 'No'}</td>
        <td>${f.quantity ?? '∞'}</td>
      </tr>`).join('') || '<tr><td colspan="3" class="dim">None</td></tr>';
}

// ── WvW ──
function renderWvw(d) {
  document.getElementById('wvw-cards').innerHTML = [
    { label: 'WvW Rank', value: d.wvw_rank ?? '—',           sub: 'account rank' },
    { label: 'WvW Team', value: d.wvw?.wvw_team ?? '—',      sub: 'current team' },
  ].map(c => `<div class="stat-card"><div class="label">${c.label}</div><div class="value">${c.value}</div><div class="sub">${c.sub}</div></div>`).join('');
}

// ── Builds ──
function renderBuilds(d) {
  const raw = d.builds || [];
  const storage = Array.isArray(raw) ? raw[0] : raw;
  const eqTabs = storage?.equipment_tabs || [];
  const buildTabs = storage?.build_tabs || [];
  let html = '';

  if (eqTabs.length) {
    html += `<div class="section-title">Equipment Templates (${eqTabs.length})</div>`;
    html += eqTabs.map(t => {
      const items = (t.equipment || []).map(eq => {
        const icon = itemIcon(eq.id);
        return `<span style="display:inline-block;margin:4px;text-align:center">
          ${icon ? `<img src="${icon}" width="32" height="32" style="border-radius:3px;display:block">` : '<div style="width:32px;height:32px;background:#333;border-radius:3px"></div>'}
          <span style="font-size:10px;color:var(--text-dim)">${itemName(eq.id)?.slice(0,12) || '#' + eq.id}</span>
        </span>`;
      }).join('');
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px">
        <div style="font-weight:600;color:var(--gold);margin-bottom:8px">${t.name || `Tab ${t.tab}`}</div>
        <div>${items || '<span class="dim">Empty</span>'}</div>
      </div>`;
    }).join('');
  }

  if (buildTabs.length) {
    html += `<div class="section-title">Build Templates (${buildTabs.length})</div>`;
    html += buildTabs.map(t => `
      <div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px">
        <div style="font-weight:600;color:var(--gold)">${t.name || `Tab ${t.tab}`}</div>
        <div class="dim" style="font-size:12px;margin-top:4px;word-break:break-all">Build ID: ${t.build?.slice(0,80) || '—'}</div>
      </div>`).join('');
  }

  if (!html) {
    html = '<div class="dim">No saved builds or equipment templates found.</div>';
  }
  document.getElementById('builds-content').innerHTML = html;
}

// ── Holdings toggle & filter ──
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

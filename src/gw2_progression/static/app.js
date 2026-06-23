import {
  MAX_CACHE_SIZE, _itemCache, _currencyCache, _matCatCache, _masteryCache, _mapCache,
  _skinCache, _colorCache, _guildCache,
  backendResolve, backendResolveSingle, cappedCacheAdd,
  resolveItems, resolveCurrencies, resolveMatCategories, resolveMasteries,
  resolveMaps, resolveSkins, resolveGuilds, resolveColors, resolveSearch,
  rgbToHex, itemName, itemIcon, currencyName, matCatName, masteryName,
  masteryRegion, mapName, skinName, skinIcon, colorHex, fmtCoin, fmtCoinShort,
  getAccountData, setAccountData,
} from './app-shared.js';

import { renderValue, renderValueCharts, filterHoldings } from './app-value.js';
import { renderCharacters, setupWardrobe, renderWallet, renderInventory, renderProgression, renderPvp, renderUnlocks, renderWvw, renderBuilds } from './app-characters.js';
import { loadGoals, createGoal, refreshGoalUI, deleteGoalUI, setGoalsStatus } from './app-goals.js';
import { getValueCharts } from './app-shared.js';

let _valueData = null;
let _abortController = null;
let _sessionToken = null;

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
  if (btn.dataset.tab === 'value' && _valueData && !getValueCharts()._rendered) {
    renderValueCharts(_valueData);
  }
});

// ── Analyze ──
document.getElementById('analyze-btn').addEventListener('click', runAnalyze);
document.getElementById('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') runAnalyze(); });

function setStep(step, state) {
  const el = document.querySelector(`.step-badge[data-step="${step}"]`);
  if (el) {
    el.classList.remove('active', 'done');
    if (state) el.classList.add(state);
  }
}
function resetSteps() {
  document.querySelectorAll('.step-badge').forEach(el => el.classList.remove('active', 'done'));
  document.getElementById('progress-steps').classList.remove('hidden');
}
function showStepProgress(steps) {
  resetSteps();
  let i = 0;
  const tick = () => {
    if (i < steps.length) {
      const prev = steps[i - 1];
      if (prev) setStep(prev, 'done');
      setStep(steps[i], 'active');
      i++;
      setTimeout(tick, 800);
    }
  };
  tick();
}

const ANALYZE_STEPS = ['tokeninfo','account','characters','wallet','bank','materials','inventory','achievements','masteries','builds','guilds','pvp','tp','unlocks','wvw','done'];

async function runAnalyze() {
  const rawKey = document.getElementById('key-input').value.trim();
  if (!rawKey) {
    const msg = document.getElementById('status-msg');
    msg.className = 'error';
    msg.textContent = 'Please paste a GW2 API key first.';
    return;
  }
  showStepProgress(ANALYZE_STEPS);
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
    setAccountData(data);

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

const _renderedTabs = new Set();

function ensureTabRendered(tab) {
  if (_renderedTabs.has(tab)) return;
  _renderedTabs.add(tab);
  const d = getAccountData();
  if (!d) return;
  const tabRender = {
    value: () => renderValue && renderValue(_valueData),
    characters: () => renderCharacters && renderCharacters(d.characters || []),
    wardrobe: () => setupWardrobe && setupWardrobe(d.unlocked_skins || []),
    wallet: () => renderWallet && renderWallet(d.wallet || []),
    inventory: () => renderInventory && renderInventory(d),
    progression: () => renderProgression && renderProgression(d),
    pvp: () => renderPvp && renderPvp(d),
    unlocks: () => renderUnlocks && renderUnlocks(d),
    wvw: () => renderWvw && renderWvw(d),
    builds: () => renderBuilds && renderBuilds(d),
  };
  if (tabRender[tab]) tabRender[tab]();
}

function renderAll(d) {
  document.querySelectorAll('.tab-loading').forEach(el => el.remove());
  document.getElementById('results').classList.remove('hidden');
  document.getElementById('nav-tabs').classList.remove('hidden');
  _renderedTabs.clear();
  // Render overview immediately (it's the active tab)
  renderOverview(d);
  _renderedTabs.add('overview');
  const exportBtn = document.getElementById('export-report-btn');
  if (exportBtn) exportBtn.disabled = false;
  loadReportHistory();
  loadSubscription();
  loadGuild();
  loadScopeExplanations();
}

// Lazy-render tabs on first click
document.getElementById('nav-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (btn) ensureTabRendered(btn.dataset.tab);
});

// ── Overview: Action Center ──
function renderOverview(d) {
  // ── 1. Hero Metrics ──
  const vs = _valueData?.summary || {};
  const totalGold = Math.floor((vs.total_value_buy || 0) / 10000);
  const walletGold = Math.floor(((d.wallet || []).find(w => w.id === 1)?.value || 0) / 10000);
  const charCount = (d.characters || []).length;
  const skinCount = d.unlocked_skins_count || 0;

  document.getElementById('hero-metrics').innerHTML = [
    { icon: '💰', label: 'Total Value', value: `${totalGold.toLocaleString()}g`, sub: 'across all assets', color: 'var(--gold-light)' },
    { icon: '🪙', label: 'Wallet', value: `${walletGold.toLocaleString()}g`, sub: 'liquid gold', color: '#6bc46b' },
    { icon: '👤', label: 'Characters', value: charCount, sub: `${skinCount} skins`, color: '#5a9e9e' },
  ].map(h => `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:28px;margin-bottom:4px">${h.icon}</div>
    <div style="font-size:12px;color:var(--text-dim)">${h.label}</div>
    <div style="font-size:24px;font-weight:700;color:${h.color}">${h.value}</div>
    <div style="font-size:11px;color:var(--text-dim)">${h.sub}</div>
  </div>`).join('');

  // ── 2. Today You Should Do ──
  const todayActions = [];
  if (totalGold > 0) {
    todayActions.push({ icon: '💰', priority: 'P0', text: `你的账号总资产价值 ${totalGold.toLocaleString()}g。查看 Top Items 了解最值钱的资产。`, action: 'Value', tab: 'value' });
  }
  const chars = d.characters || [];
  if (chars.length) {
    const maxLevel = chars.filter(c => c.level === 80).length;
    if (maxLevel < chars.length) {
      todayActions.push({ icon: '⬆', priority: 'P1', text: `你有 ${chars.length - maxLevel} 个角色未满级。提升到 80 级以解锁 Build 推荐。`, action: 'Level Up', tab: 'characters' });
    }
    const profs = new Set(chars.map(c => c.profession));
    if (profs.size < 3) {
      todayActions.push({ icon: '🎭', priority: 'P1', text: `只有 ${profs.size} 个职业。创建新角色体验不同玩法。`, action: 'New Character', tab: 'characters' });
    }
  }
  if (skinCount > 0 && skinCount < 200) {
    todayActions.push({ icon: '🎨', priority: 'P2', text: `${skinCount} 皮肤已解锁。通过地图完成和收藏获取更多皮肤。`, action: 'Wardrobe', tab: 'wardrobe' });
  }
  if (_valueData?.summary?.unpriced_item_count > 0) {
    todayActions.push({ icon: '❓', priority: 'P1', text: `${_valueData.summary.unpriced_item_count} 件物品缺少价格数据。添加 tradingpost 权限以自动定价。`, action: 'Fix Permissions', tab: 'value' });
  }

  const todaySection = document.getElementById('today-section');
  const todayList = document.getElementById('today-list');
  if (todayActions.length) {
    todaySection.style.display = 'block';
    todayList.innerHTML = todayActions.map(a => `
      <div style="display:flex;align-items:center;gap:10px;background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:10px 14px;cursor:pointer"
           onclick="document.querySelector('[data-tab=${a.tab}]')?.click()">
        <span style="font-size:18px">${a.icon}</span>
        <span style="font-size:11px;background:${a.priority === 'P0' ? '#5a3a1a' : a.priority === 'P1' ? '#2a3a2a' : '#1a2a3a'};color:${a.priority === 'P0' ? '#d0a050' : a.priority === 'P1' ? '#6bc46b' : '#5a9ece'};padding:1px 6px;border-radius:3px;font-weight:600">${a.priority}</span>
        <span style="flex:1;font-size:13px">${a.text}</span>
        <span style="font-size:12px;color:var(--gold)">${a.action} →</span>
      </div>
    `).join('');
  }

  // ── 3. Progression Timeline ──
  const days = ['Day 1','Day 2','Day 3','Day 4','Day 5','Day 6','Day 7'];
  const timelineTasks = [];
  if (chars.length) timelineTasks.push('Level remaining characters to 80');
  if (walletGold > 0) timelineTasks.push('Sell high-value materials from storage');
  if (skinCount < 100) timelineTasks.push('Complete map completion for skins');
  timelineTasks.push('Check crafting dailies for time-gated materials');
  timelineTasks.push('Review Trading Post for profitable flips');
  timelineTasks.push('Run T4 Fractals for ascended gear');
  if (timelineTasks.length < 7) timelineTasks.push('Farm Winterberry / Volatile Magic for trophies');
  if (timelineTasks.length < 7) timelineTasks.push('Complete world boss trains for gold');
  if (timelineTasks.length < 7) timelineTasks.push('Work on legendary collections');
  if (timelineTasks.length < 7) timelineTasks.push('Participate in guild missions');

  const timelineSection = document.getElementById('timeline-section');
  const timelineGrid = document.getElementById('timeline-grid');
  if (timelineTasks.length) {
    timelineSection.style.display = 'block';
    timelineGrid.innerHTML = days.map((day, i) => {
      const task = timelineTasks[i % timelineTasks.length];
      const done = i === 0 ? '0%' : i === 1 ? '15%' : i === 2 ? '30%' : i === 3 ? '45%' : i === 4 ? '60%' : i === 5 ? '75%' : '90%';
      const color = i === 0 ? '#5a3a1a' : i === 1 ? '#2a4a2a' : i === 2 ? '#1a3a4a' : i === 3 ? '#2a2a4a' : i === 4 ? '#4a2a4a' : i === 5 ? '#4a3a1a' : '#1a4a3a';
      return `<div style="background:${color};border:1px solid var(--border);border-radius:8px;padding:10px;position:relative;overflow:hidden">
        <div style="position:absolute;bottom:0;left:0;height:3px;width:${done};background:var(--gold);border-radius:0 2px 0 0"></div>
        <div style="font-size:11px;font-weight:600;color:var(--gold);margin-bottom:4px">${day}</div>
        <div style="font-size:11px;color:var(--text)">${task}</div>
        <div style="font-size:10px;color:var(--text-dim);margin-top:4px">${done} complete</div>
      </div>`;
    }).join('');
  }

  // ── 4. Quick Stats ──
  const stats = [
    { label: 'Total Value', value: `${Math.floor((vs.total_value_buy || 0) / 10000).toLocaleString()}g`, sub: `${vs.priced_item_count || 0} items` },
    { label: 'Wallet', value: `${walletGold.toLocaleString()}g`, sub: 'liquid gold' },
    { label: 'Materials', value: `${Math.floor((vs.material_value_buy || 0) / 10000).toLocaleString()}g`, sub: 'material storage' },
    { label: 'Bank', value: `${Math.floor((vs.bank_value_buy || 0) / 10000).toLocaleString()}g`, sub: 'bank items' },
    { label: 'Characters', value: charCount, sub: `${[...new Set(chars.map(c => c.profession))].length} professions` },
    { label: 'Skins', value: skinCount, sub: `${d.unlocked_dyes_count || 0} dyes` },
  ];
  document.getElementById('quick-stats').innerHTML = stats.map(s => `
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:12px">
      <div style="font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px">${s.label}</div>
      <div style="font-size:18px;font-weight:600;color:var(--gold-light)">${s.value}</div>
      <div style="font-size:11px;color:var(--text-dim)">${s.sub}</div>
    </div>
  `).join('');

  // ── 4. Account Details (collapsed) ──
  const created = d.account_created ? new Date(d.account_created).toLocaleDateString() : '—';
  const cards = [
    { label: 'Account',       value: d.account_name || '—',              sub: `World ${d.account_world}` },
    { label: 'Created',       value: created,                            sub: 'account created' },
    { label: 'Playtime',      value: `${d.account_age_hours}h`,          sub: 'total hours' },
    { label: 'Fractal Level', value: d.fractal_level ?? '—',             sub: 'highest tier' },
    { label: 'Daily AP',      value: (d.daily_ap ?? 0).toLocaleString(), sub: 'achievement points' },
    { label: 'Monthly AP',    value: (d.monthly_ap ?? 0).toLocaleString(),sub: 'monthly achievements' },
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

  const accountName = getAccountData()?.account_name;
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



async function exportReport() {
  const btn = document.getElementById('export-report-btn');
  const status = document.getElementById('export-status');
  const data = getAccountData();
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
  const data = getAccountData();
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

// ── Credential Management ──
async function loadProviders() {
  try {
    const res = await fetch("/credentials/providers");
    if (!res.ok) return;
    const providers = await res.json();
    const sel = document.getElementById("cred-provider");
    sel.innerHTML = '<option value="">Select provider…</option>' +
      providers.map(p => `<option value="${p.id}">${p.name}</option>`).join("");
  } catch (e) { /* ignore */ }
}

async function loadCredentials() {
  const list = document.getElementById("credential-list");
  try {
    const res = await fetch("/credentials");
    if (!res.ok) { list.innerHTML = '<div class="dim">Failed to load credentials.</div>'; return; }
    const creds = await res.json();
    if (!creds.length) {
      list.innerHTML = '<div class="dim">No saved API keys. Add one below.</div>';
      return;
    }
    list.innerHTML = '<div style="display:flex;flex-direction:column;gap:6px">' +
      creds.map(c => `<div style="display:flex;justify-content:space-between;align-items:center;background:var(--bg2);border:1px solid var(--border);padding:8px 12px;border-radius:4px;font-size:13px">
        <span><strong>${c.provider}</strong> ${c.label ? '— ' + c.label : ''} <span class="dim">${c.fingerprint}</span></span>
        <span class="dim">${c.last_used_at ? 'Last used: ' + c.last_used_at.slice(0, 10) : ''}</span>
        <button class="btn-sm" style="color:#c07070" data-cred-id="${c.id}">Delete</button>
      </div>`).join("") + '</div>';
    list.querySelectorAll("[data-cred-id]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.credId;
        try {
          await fetch(`/credentials/${id}`, { method: "DELETE" });
          loadCredentials();
        } catch (e) { /* ignore */ }
      });
    });
  } catch (e) { /* ignore */ }
}

document.getElementById("cred-save-btn")?.addEventListener("click", async () => {
  const provider = document.getElementById("cred-provider").value;
  const label = document.getElementById("cred-label").value;
  const apiKey = document.getElementById("cred-key").value;
  const status = document.getElementById("cred-status");
  if (!provider || !apiKey) { status.textContent = "Provider and API key are required."; return; }
  try {
    const res = await fetch("/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey, label }),
    });
    if (!res.ok) { status.textContent = "Failed to save."; return; }
    status.textContent = "Credential saved.";
    document.getElementById("cred-key").value = "";
    document.getElementById("cred-label").value = "";
    loadCredentials();
  } catch (e) { status.textContent = `Error: ${e.message}`; }
});

// ── Permission Explanations ──
async function loadScopeExplanations() {
  const grid = document.getElementById("perm-grid");
  if (!grid || grid.children.length > 0) return;
  try {
    const res = await fetch("/credentials/providers");
    if (!res.ok) return;
    const data = await res.json();
    const ex = data.scope_explanations || {};
    grid.innerHTML = Object.entries(ex).map(([scope, desc]) =>
      `<div class="perm-item"><span class="perm-badge granted">${scope}</span><span class="dim">${desc}</span></div>`
    ).join("");
  } catch (e) { /* ignore */ }
}

// ── Subscription Management ──
async function loadSubscription() {
  const data = getAccountData();
  if (!data) return;
  const statusEl = document.getElementById("sub-status");
  try {
    const res = await fetch(`/subscriptions/${encodeURIComponent(data.account_name)}`);
    const sub = await res.json();
    if (sub.active) {
      statusEl.textContent = `Active — ${sub.report_type} report${sub.email ? ' to ' + sub.email : ''}.`;
      document.getElementById("sub-btn").textContent = "Cancel";
    } else {
      statusEl.textContent = "Not subscribed.";
      document.getElementById("sub-btn").textContent = "Subscribe";
    }
  } catch (e) { /* ignore */ }
}

document.getElementById("sub-btn")?.addEventListener("click", async () => {
  const data = getAccountData();
  if (!data) { document.getElementById("sub-status").textContent = "Run analysis first."; return; }
  const btn = document.getElementById("sub-btn");
  const statusEl = document.getElementById("sub-status");
  if (btn.textContent === "Cancel") {
    try {
      const res = await fetch(`/subscriptions/${encodeURIComponent(data.account_name)}`, { method: "DELETE" });
      if (res.ok) { statusEl.textContent = "Cancelled."; btn.textContent = "Subscribe"; }
    } catch (e) { statusEl.textContent = `Error: ${e.message}`; }
    return;
  }
  const email = document.getElementById("sub-email").value;
  if (!email) { statusEl.textContent = "Please enter your email."; return; }
  try {
    const res = await fetch("/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_name: data.account_name, email, report_type: "weekly" }),
    });
    if (res.ok) { statusEl.textContent = "Subscribed!"; btn.textContent = "Cancel"; }
    else { statusEl.textContent = "Failed to subscribe."; }
  } catch (e) { statusEl.textContent = `Error: ${e.message}`; }
});

// ── Guild Workspace ──
async function loadGuild() {
  const data = getAccountData();
  if (!data) return;
  const statusEl = document.getElementById("guild-status");
  const membersEl = document.getElementById("guild-members");
  const aggEl = document.getElementById("guild-aggregate");
  try {
    const res = await fetch(`/guild/by-account/${encodeURIComponent(data.account_name)}`);
    if (!res.ok) { statusEl.textContent = "Not in a guild."; membersEl.innerHTML = ""; aggEl.innerHTML = ""; return; }
    const guild = await res.json();
    if (!guild) { statusEl.textContent = "Not in a guild."; return; }
    statusEl.innerHTML = `<strong>${guild.name}</strong> — Code: <code>${guild.invite_code}</code> — ${guild.members.length} member(s)`;
    membersEl.innerHTML = "<div class='section-title'>Members</div>" +
      guild.members.map(m => `<div style="padding:4px 0;font-size:13px"><span>${m.account_name}</span> <span class="dim">(${m.role})</span></div>`).join("");

    // Load aggregate
    const aggRes = await fetch(`/guild/${guild.id}/aggregate`);
    if (aggRes.ok) {
      const agg = await aggRes.json();
      aggEl.innerHTML = `<div class="section-title">Combined Stats</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;font-size:13px">
          <div class="stat-card"><div class="label">Members</div><div class="value">${agg.member_count}</div></div>
          <div class="stat-card"><div class="label">Total Wallet Gold</div><div class="value">${agg.total_wallet_gold / 10000}g</div></div>
          <div class="stat-card"><div class="label">Total Characters</div><div class="value">${agg.total_characters}</div></div>
          <div class="stat-card"><div class="label">Total Skins</div><div class="value">${agg.total_skins}</div></div>
        </div>`;
    }
  } catch (e) { statusEl.textContent = `Error: ${e.message}`; }
}

document.getElementById("guild-create-btn")?.addEventListener("click", async () => {
  const data = getAccountData();
  const key = document.getElementById("key-input").value.trim();
  const name = document.getElementById("guild-name").value;
  if (!data || !key || !name) { document.getElementById("guild-status").textContent = "Run analysis and enter guild name."; return; }
  try {
    const res = await fetch("/guild/create", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, account_name: data.account_name, api_key: key }),
    });
    if (res.ok) { document.getElementById("guild-status").textContent = "Guild created!"; loadGuild(); }
    else { document.getElementById("guild-status").textContent = "Failed to create."; }
  } catch (e) { document.getElementById("guild-status").textContent = `Error: ${e.message}`; }
});

document.getElementById("guild-join-btn")?.addEventListener("click", async () => {
  const data = getAccountData();
  const key = document.getElementById("key-input").value.trim();
  const code = document.getElementById("guild-invite").value;
  if (!data || !key || !code) { document.getElementById("guild-status").textContent = "Run analysis and enter invite code."; return; }
  try {
    const res = await fetch("/guild/join", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite_code: code, account_name: data.account_name, api_key: key }),
    });
    if (res.ok) { document.getElementById("guild-status").textContent = "Joined guild!"; loadGuild(); }
    else { document.getElementById("guild-status").textContent = "Invalid invite code."; }
  } catch (e) { document.getElementById("guild-status").textContent = `Error: ${e.message}`; }
});

// ── Products Tab ──
async function loadProducts() {
  const grid = document.getElementById("product-grid");
  try {
    const res = await fetch("/commerce/products");
    if (!res.ok) return;
    const products = await res.json();
    grid.innerHTML = products.map(p => `
      <div style="background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:16px">
        <div style="font-size:15px;font-weight:600;color:var(--gold);margin-bottom:6px">${p.name}</div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">${p.description}</div>
        <div style="font-size:13px;margin-bottom:8px">
          <span class="gold-val">${p.price_gold >= 1 ? p.price_gold.toFixed(1) + 'g' : (p.price_copper / 100).toFixed(0) + 's'}</span>
          <span class="dim"> (${p.type})</span>
        </div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">
          ${p.deliverables.map(d => '<span style="background:var(--bg3);padding:2px 6px;border-radius:3px;margin:2px;display:inline-block">' + d + '</span>').join("")}
        </div>
        <button class="btn-sm buy-btn" data-product='${JSON.stringify(p).replace(/"/g, "&quot;")}'>Buy Now</button>
      </div>
    `).join("");
    grid.querySelectorAll(".buy-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const p = JSON.parse(btn.dataset.product.replace(/&quot;/g, '"'));
        const email = prompt("Enter your email for delivery:", "");
        if (!email) return;
        const ref = prompt("Referral code (optional):", "");
        const url = ref ? "/affiliates/purchase" : "/commerce/orders";
        const body = ref
          ? JSON.stringify({ product_id: p.id, customer_email: email, referral_code: ref })
          : JSON.stringify({ product_id: p.id, customer_email: email });
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
        }).then(r => r.json()).then(order => {
          alert(`Order placed! License key: ${order.license_key || ''}`);
        }).catch(e => alert("Error: " + e.message));
      });
    });
  } catch (e) { /* ignore */ }
}

async function loadOrders() {
  // Display orders in settings or as a section
}

// ── Affiliate ──
document.getElementById("aff-create-btn")?.addEventListener("click", async () => {
  const name = document.getElementById("aff-name").value;
  const display = document.getElementById("aff-display");
  if (!name) { display.textContent = "Enter your name."; return; }
  try {
    const res = await fetch("/affiliates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const aff = await res.json();
    display.innerHTML = `Your referral code: <code style="background:var(--bg3);padding:2px 6px;border-radius:3px">${aff.referral_code}</code> — Share this with others!`;
  } catch (e) { display.textContent = `Error: ${e.message}`; }
});

// Init credentials UI on page load
loadProviders();


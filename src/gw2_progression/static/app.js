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

  // ── Quick Actions ──
  const quickGrid = document.getElementById('quick-actions-grid');
  const quickSection = document.getElementById('quick-actions');
  const recList = document.getElementById('recommendations-list');
  const recSection = document.getElementById('top-recommendations');
  if (!quickGrid) return;

  const valueData = _valueData;
  const actions = [];
  const recs = [];

  // Build quick actions based on data
  if (valueData?.summary) {
    const s = valueData.summary;
    if (s.unpriced_item_count > 0) {
      actions.push({ icon: '💰', label: 'Unpriced Items', desc: `${s.unpriced_item_count} items need price data. Add TP permissions or check item IDs.`, tab: 'value' });
      recs.push(`Open the Items tab to review ${s.unpriced_item_count} unpriced items. Add 'tradingpost' permission for automatic pricing.`);
    }
    if (s.priced_item_count > 0) {
      actions.push({ icon: '📊', label: 'Export Report', desc: 'Generate a downloadable JSON report of your account value.', tab: 'overview', id: 'export-report-btn' });
    }
  }

  const walletGold = (d.wallet || []).find(w => w.id === 1)?.value || 0;
  const chars = d.characters || [];
  const professions = new Set(chars.map(c => c.profession));
  const maxChars = chars.length;

  if (walletGold > 0) {
    const goldDisplay = (walletGold / 10000).toFixed(1);
    actions.push({ icon: '🪙', label: 'Wallet', desc: `${goldDisplay}g total gold across account.`, tab: 'wallet' });
  }
  if (maxChars > 0) {
    actions.push({ icon: '👤', label: 'Characters', desc: `${maxChars} characters, ${professions.size} professions: ${[...professions].slice(0, 5).join(', ')}${professions.size > 5 ? '...' : ''}`, tab: 'characters' });
  }
  if (d.unlocked_skins_count > 0) {
    actions.push({ icon: '🎨', label: 'Wardrobe', desc: `${d.unlocked_skins_count} skins unlocked.`, tab: 'wardrobe' });
    if (d.unlocked_skins_count < 100) recs.push('Consider unlocking more skins through map completion and collections to increase account value.');
  }

  // Goal recommendations
  if (window._goals && window._goals.length > 0) {
    const incomplete = window._goals.filter(g => (g.progress || 0) < 100);
    if (incomplete.length > 0) {
      const nearest = incomplete.sort((a, b) => (b.progress || 0) - (a.progress || 0))[0];
      recs.push(`Your closest goal is "${nearest.name}" (${Math.round(nearest.progress || 0)}% complete). Focus on missing requirements.`);
    }
  }

  // Build recommendations
  if (window._buildReadiness && window._buildReadiness.length > 0) {
    const best = window._buildReadiness[0];
    if (best.readiness_score > 0) recs.push(`Best build match: ${best.build_name} (${Math.round(best.readiness_score * 100)}% ready, ${best.missing_items_count} items missing).`);
  }

  if (actions.length) {
    quickSection.style.display = 'block';
    quickGrid.innerHTML = actions.map(a => {
      const clickHandler = a.tab === 'overview' && a.id
        ? `onclick="document.getElementById('${a.id}').click()"`
        : a.tab ? `onclick="document.querySelector('[data-tab=${a.tab}]')?.click()"` : '';
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:12px;cursor:pointer" ${clickHandler}>
        <div style="font-size:20px;margin-bottom:4px">${a.icon}</div>
        <div style="font-size:13px;font-weight:600;color:var(--gold)">${a.label}</div>
        <div style="font-size:11px;color:var(--text-dim);margin-top:4px">${a.desc}</div>
      </div>`;
    }).join('');
  }

  if (recs.length) {
    recSection.style.display = 'block';
    recList.innerHTML = recs.map(r => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">💡 ${r}</div>`).join('');
  }
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


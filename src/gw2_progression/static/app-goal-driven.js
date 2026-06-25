// GW2 Progression OS — Goal-Driven Frontend Module
// Transforms the UI from tab navigation to goal-driven prompts + plans + reports.

import { fmtCoin, fmtCoinShort, backendResolve } from './app-shared.js';

let _currentPlanId = null;
let _currentPlan = null;
let _currentPlanResult = null;
let _sessionApiKey = '';
let _progressiveResults = [];

// ── Init ──
export function initGoalDriven(apiKey) {
  _sessionApiKey = apiKey;

  const promptInput = document.getElementById('goal-prompt-input');
  const promptBtn = document.getElementById('goal-prompt-btn');
  if (promptInput && promptBtn) {
    promptBtn.onclick = () => submitGoal(promptInput.value);
    promptInput.onkeydown = (e) => { if (e.key === 'Enter') submitGoal(promptInput.value); };
    promptInput.focus();
  }

  document.querySelectorAll('.quick-goal-card').forEach(card => {
    card.onclick = () => submitGoal(card.dataset.goal || '');
  });

  document.querySelectorAll('[data-nav]').forEach(btn => {
    btn.onclick = () => switchPage(btn.dataset.nav);
  });

  wirePricingCards();
  wireFreeReportButton();
  showTrustPanel();
}

function switchPage(page) {
  document.querySelectorAll('.page-section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('[data-nav]').forEach(b => b.classList.remove('active'));
  const target = document.getElementById(`page-${page}`);
  if (target) target.style.display = 'block';
  const navBtn = document.querySelector(`[data-nav="${page}"]`);
  if (navBtn) navBtn.classList.add('active');

  // Show report content if we have a plan
  if (page === 'report' && _currentPlan) {
    document.getElementById('report-empty').style.display = 'none';
    document.getElementById('report-content').style.display = 'block';
  }
}

function showTrustPanel() {
  // Trust panel is already in HTML, but we can add dynamic tips
  const tips = [
    'Your API key is used only in this session.',
    'No ArenaNet password is ever requested.',
    'Revoke your key anytime from account.arena.net.'
  ];
  const el = document.querySelector('.trust-banner');
  if (el) {
    el.innerHTML = tips.map(t => `<span>🔒 ${t}</span>`).join('');
  }
}

// ── Goal Submission with Progressive Loading ──
async function submitGoal(text) {
  text = text.trim();
  if (!text) return;

  showStatus('goal-status', 'Interpreting your goal…', '');
  showPage('plan');
  showProgressiveLoading();

  try {
    // Step 1: Interpret goal
    const interpRes = await fetch('/goal-driven/interpret', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal_text: text }),
    });
    if (!interpRes.ok) throw new Error(`Interpret failed: ${interpRes.status}`);
    const interpreted = await interpRes.json();
    const parsed = interpreted.parsed;
    showInterpretation(parsed);

    // Step 1b: Progressive account data (stage 1+2)
    updateProgressiveStage('📡', 'Reading account data…');
    const progRes = await fetch('/goal-driven/progressive/full', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: _sessionApiKey, goal_text: text }),
    });
    if (progRes.ok) {
      const progData = await progRes.json();
      _progressiveResults = progData.stages || [];
      showProgressiveResults(_progressiveResults);
    }

    // Step 2: Generate plan (longer operation)
    updateProgressiveStage('🧠', 'Building your action plan…');
    const genRes = await fetch('/goal-driven/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: _sessionApiKey,
        goal_text: text,
        strategy: parsed.strategy || 'balanced',
      }),
    });
    if (!genRes.ok) throw new Error(`Generate failed: ${genRes.status}`);
    const result = await genRes.json();
    _currentPlan = result.plan;
    _currentPlanId = result.plan.plan_id;
    _currentPlanResult = result;

    updateProgressiveStage('✅', 'Plan ready!');
    renderPlan(result);
    showStatus('goal-status', '✅ Plan generated!', 'success');
  } catch (err) {
    console.error('Goal submission error:', err);
    showStatus('goal-status', `Error: ${err.message}`, 'error');
    document.getElementById('plan-content').innerHTML =
      `<div class="error-box">Failed to generate plan: ${err.message}</div>`;
  }
}

function showProgressiveLoading() {
  const container = document.getElementById('plan-content');
  if (!container) return;
  container.innerHTML = `
    <div id="progressive-container" style="margin-bottom:20px">
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px">🔍 ANALYZING YOUR ACCOUNT</div>
      <div id="progressive-steps" style="display:flex;flex-direction:column;gap:8px">
        <div class="prog-step" data-stage="1" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;opacity:0.6">
          <span class="prog-icon">⏳</span>
          <span class="prog-label" style="flex:1;font-size:13px">Account basics</span>
          <span class="prog-status" style="font-size:11px;color:var(--text-dim)">pending</span>
        </div>
        <div class="prog-step" data-stage="2" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;opacity:0.4">
          <span class="prog-icon">⏳</span>
          <span class="prog-label" style="flex:1;font-size:13px">Valuation estimate</span>
          <span class="prog-status" style="font-size:11px;color:var(--text-dim)">pending</span>
        </div>
        <div class="prog-step" data-stage="3" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;opacity:0.3">
          <span class="prog-icon">⏳</span>
          <span class="prog-label" style="flex:1;font-size:13px">Build & goal analysis</span>
          <span class="prog-status" style="font-size:11px;color:var(--text-dim)">pending</span>
        </div>
        <div class="prog-step" data-stage="4" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;opacity:0.2">
          <span class="prog-icon">⏳</span>
          <span class="prog-label" style="flex:1;font-size:13px">Full plan generation</span>
          <span class="prog-status" style="font-size:11px;color:var(--text-dim)">pending</span>
        </div>
      </div>
    </div>
    <div id="plan-content-after" style="text-align:center;padding:20px;color:var(--text-dim)">
      <span class="spinner"></span> Loading data…
    </div>`;
}

function updateProgressiveStage(icon, label) {
  const container = document.getElementById('progressive-container');
  if (!container) return;
  const statusEl = container.querySelector('.prog-step:last-child .prog-status');
  if (statusEl) statusEl.textContent = `${icon} ${label}`;
}

function showProgressiveResults(stages) {
  if (!stages || stages.length === 0) return;

  stages.forEach(stage => {
    const stepEl = document.querySelector(`.prog-step[data-stage="${stage.stage}"]`);
    if (!stepEl) return;

    const icon = stepEl.querySelector('.prog-icon');
    const label = stepEl.querySelector('.prog-label');
    const status = stepEl.querySelector('.prog-status');

    stepEl.style.opacity = '1';
    stepEl.style.borderColor = stage.error ? 'var(--red)' : 'var(--green)';

    if (stage.error) {
      icon.textContent = '⚠️';
      if (status) status.textContent = `⚠️ ${stage.error}`;
      return;
    }

    if (stage.stage === 1) {
      icon.textContent = '👤';
      if (label) label.textContent = `Account: ${stage.account_name}`;
      if (status) status.textContent = `💰 ${stage.wallet_gold_display || fmtCoinShort(stage.wallet_gold)}`;
    } else if (stage.stage === 2) {
      icon.textContent = '💰';
      if (label) label.textContent = `Total value: ${stage.total_value_display || '0g'}`;
      if (status) status.textContent = `💎 ${stage.hidden_wealth_display || '0g'} hidden`;
    } else if (stage.stage === 3) {
      icon.textContent = '🎯';
      const name = stage.closest_goal_name || stage.best_build_name || 'analysis';
      if (label) label.textContent = `Best match: ${name}`;
      if (status) status.textContent = `📋 ${stage.first_action || 'ready'}`;
    } else if (stage.stage === 4) {
      icon.textContent = '✅';
      if (label) label.textContent = stage.insight || 'Plan ready';
      if (status) status.textContent = `📅 ${stage.estimated_days || 7} days`;
    }
  });
}

// ── Show Interpretation ──
function showInterpretation(parsed) {
  const el = document.getElementById('interpretation-display');
  if (!el) return;

  const goalTypes = {
    MAKE_GOLD: '💰 Make Gold',
    FINISH_LEGENDARY: '⚔️ Finish Legendary',
    PREPARE_BUILD: '🛡️ Prepare Build',
    OPTIMIZE_INVENTORY: '📦 Optimize Inventory',
    CRAFT_ITEM: '🔨 Craft Item',
    WEEKLY_PLAN: '📆 Weekly Plan',
    GENERIC: '🎯 General Goal',
  };

  el.style.display = 'block';
  el.innerHTML = `
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
        <span style="font-size:16px">${goalTypes[parsed.goal_type] || '🎯 Goal'}</span>
        <span style="font-size:20px;color:var(--gold);font-weight:600">${parsed.target_item_name || parsed.raw_text}</span>
        <span style="font-size:12px;color:var(--text-dim)">confidence: ${(parsed.confidence * 100).toFixed(0)}%</span>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:12px">
        ${parsed.strategy !== 'balanced' ? `<span style="background:var(--bg3);padding:3px 8px;border-radius:4px;border:1px solid var(--border)">Strategy: ${parsed.strategy}</span>` : ''}
        ${parsed.time_budget_minutes ? `<span style="background:var(--bg3);padding:3px 8px;border-radius:4px;border:1px solid var(--border)">⏱ ${parsed.time_budget_minutes}min/day</span>` : ''}
        ${parsed.game_mode ? `<span style="background:var(--bg3);padding:3px 8px;border-radius:4px;border:1px solid var(--border)">🎮 ${parsed.game_mode}</span>` : ''}
      </div>
    </div>
  `;
}

// ── Render Plan ──
function renderPlan(result) {
  const plan = result.plan;
  const actions = plan.actions || [];
  const insight = result.insight || '';
  const topActions = result.top_actions || [];
  const sevenDay = result.seven_day_plan || [];

  const container = document.getElementById('plan-content');
  if (!container) return;

  let html = '';

  // ── Insight Banner ──
  const totalGold = fmtCoinShort(plan.total_cost_copper);
  html += `
    <div class="insight-card">
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:6px">📊 INSIGHT</div>
      <div style="font-size:18px;color:var(--gold);font-weight:600">${insight || 'Plan generated'}</div>
      <div style="display:flex;gap:12px;margin-top:10px;flex-wrap:wrap;font-size:12px">
        <span style="background:var(--bg3);padding:4px 10px;border-radius:4px">📅 ${plan.estimated_days} day plan</span>
        <span style="background:var(--bg3);padding:4px 10px;border-radius:4px">💰 ${totalGold} total</span>
        <span style="background:var(--bg3);padding:4px 10px;border-radius:4px">🎯 ${plan.completion_percent.toFixed(0)}% completion</span>
        <span style="background:var(--bg3);padding:4px 10px;border-radius:4px">⚡ ${plan.strategy} strategy</span>
      </div>
    </div>`;

  // ── Top 3 Actions ──
  if (topActions.length > 0) {
    html += `<div class="section-title" style="margin-top:0;font-size:13px">🎯 YOUR TOP ACTIONS</div>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px" id="plan-top-actions-container">`;
    topActions.forEach((a, i) => { html += renderActionCard(a, i + 1); });
    html += `</div>`;
  }

  // ── 7-Day Plan ──
  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  html += `<div class="section-title" style="font-size:13px">📆 YOUR 7-DAY PLAN</div>
    <div id="seven-day-container" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-bottom:20px">`;
  sevenDay.forEach((dayActions, dayIdx) => {
    if (dayIdx >= 7) return;
    html += `
      <div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px">
        <div style="font-size:12px;color:var(--gold);font-weight:600;margin-bottom:6px">${dayNames[dayIdx]}</div>
        ${dayActions.length === 0 ? '<div style="font-size:11px;color:var(--text-dim)">Rest or flex</div>' : ''}
        ${dayActions.slice(0, 2).map(a => `
          <div style="font-size:11px;color:var(--text);padding:3px 0;border-bottom:1px solid var(--border)">${a.title}</div>
        `).join('')}
      </div>`;
  });
  html += `</div>`;

  // ── Strategy Selector ──
  html += `
    <div style="margin-bottom:16px">
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:6px">⚙️ ADJUST STRATEGY</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${['balanced','cheapest','fastest','gold_first','build_first','low_effort'].map(s => `
          <button class="strategy-btn ${s === plan.strategy ? 'active' : ''}" data-strategy="${s}" style="background:${s === plan.strategy ? 'var(--gold)' : 'var(--bg3)'};border:1px solid var(--border);border-radius:4px;color:${s === plan.strategy ? '#111' : 'var(--text)'};padding:6px 14px;font-size:12px;cursor:pointer">${s.replace('_', ' ').toUpperCase()}</button>
        `).join('')}
      </div>
    </div>`;

  // ── Revision Box ──
  html += `
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:8px">💬 Refine Your Plan</div>
      <div style="display:flex;gap:8px">
        <input id="revision-input" type="text" placeholder='e.g. "Make it cheaper" or "Focus on gold"' style="flex:1;background:var(--bg3);border:1px solid var(--border);border-radius:4px;color:var(--text-bright);padding:10px 14px;font-size:13px;outline:none" />
        <button id="revision-btn" style="background:var(--gold);border:none;border-radius:4px;color:#111;padding:10px 20px;font-size:13px;font-weight:600;cursor:pointer">Refine</button>
      </div>
      <div id="revision-result" style="margin-top:8px;font-size:12px;color:var(--text-dim)"></div>
    </div>`;

  // ── Report / Export ──
  html += `
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button id="generate-report-btn" style="background:var(--gold);border:none;border-radius:4px;color:#111;padding:10px 24px;font-size:13px;font-weight:600;cursor:pointer">📄 Generate Report</button>
      <button onclick="exportPlanText()" style="background:var(--bg3);border:1px solid var(--border);border-radius:4px;color:var(--text);padding:10px 24px;font-size:13px;cursor:pointer">📋 Copy Plan</button>
      <button onclick="navigateToReport()" style="background:var(--bg3);border:1px solid var(--border);border-radius:4px;color:var(--text);padding:10px 24px;font-size:13px;cursor:pointer">📊 View Report →</button>
    </div>
    <div id="report-preview" style="margin-top:12px"></div>`;

  container.innerHTML = html;
  wirePlanActions(result);
}

function renderActionCard(action, idx) {
  const typeIcons = {
    SELL_ITEM: '💰', BUY_ITEM: '🛒', CRAFT_ITEM: '🔨',
    FARM_ACTIVITY: '⚔️', COMPLETE_ACHIEVEMENT: '🏆',
    IMPROVE_BUILD: '⬆️', CLEAN_INVENTORY: '🧹',
  };
  const icon = typeIcons[action.action_type] || '•';
  const rewardStr = action.reward_gold > 0 ? `+${fmtCoinShort(action.reward_gold)}` : '';
  const costStr = action.cost_gold > 0 ? `${fmtCoinShort(action.cost_gold)}` : '';

  return `
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px;display:flex;align-items:center;gap:12px">
      <div style="font-size:24px;width:32px;text-align:center">${icon}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:14px;color:var(--text-bright);font-weight:600">${idx}. ${action.title}</div>
        <div style="font-size:12px;color:var(--text-dim);margin-top:2px">${action.reason}</div>
      </div>
      <div style="text-align:right;flex-shrink:0;font-size:12px">
        ${rewardStr ? `<div style="color:var(--green)">${rewardStr}</div>` : ''}
        ${costStr ? `<div style="color:var(--red)">${costStr}</div>` : ''}
        <div style="color:var(--text-dim);font-size:11px">${action.time_cost_minutes}m</div>
      </div>
    </div>`;
}

function wirePlanActions(result) {
  const revInput = document.getElementById('revision-input');
  const revBtn = document.getElementById('revision-btn');
  if (revInput && revBtn) {
    revBtn.onclick = () => submitRevision(revInput.value);
    revInput.onkeydown = (e) => { if (e.key === 'Enter') submitRevision(revInput.value); };
  }

  document.querySelectorAll('.strategy-btn').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.strategy-btn').forEach(b => {
        b.style.background = 'var(--bg3)';
        b.style.color = 'var(--text)';
      });
      btn.style.background = 'var(--gold)';
      btn.style.color = '#111';
      submitRevision(`change strategy to ${btn.dataset.strategy}`);
    };
  });

  const reportBtn = document.getElementById('generate-report-btn');
  if (reportBtn) reportBtn.onclick = generateReport;

  window.exportPlanText = () => {
    const text = planToText(result);
    navigator.clipboard?.writeText(text).then(() => {
      showStatus('revision-result', '✅ Plan copied to clipboard!', 'success');
    }).catch(() => {
      showStatus('revision-result', '✅ Plan ready to paste (copy manually)', '');
    });
  };

  window.navigateToReport = () => switchPage('report');
}

// ── Revision ──
async function submitRevision(text) {
  text = text.trim();
  if (!text || !_currentPlanId) return;

  const resultEl = document.getElementById('revision-result');
  if (resultEl) resultEl.innerHTML = '<span class="spinner"></span> Revising plan…';

  try {
    const res = await fetch('/goal-driven/revise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plan_id: _currentPlanId,
        revision_text: text,
        api_key: _sessionApiKey,
      }),
    });
    if (!res.ok) throw new Error(`Revision failed: ${res.status}`);
    const data = await res.json();

    _currentPlan = data.revised_plan;
    _currentPlanResult.plan = data.revised_plan;

    if (resultEl) {
      resultEl.innerHTML = `
        <div style="background:#1a2a1a;border:1px solid #3a5a3a;border-radius:6px;padding:10px;margin-bottom:12px">
          <div style="color:var(--green);font-size:13px;font-weight:600">✅ Plan Updated</div>
          <div style="font-size:12px;color:var(--text);margin-top:4px">${data.delta_summary}</div>
          ${data.changed_actions.length > 0 ? `<div style="font-size:11px;color:var(--text-dim);margin-top:4px">Top: ${data.changed_actions.join(', ')}</div>` : ''}
        </div>`;
    }

    _currentPlanResult.top_actions = data.revised_plan.actions.slice(0, 3);
    renderActionsOnly(data.revised_plan);
    renderSevenDayOnly(data.revised_plan);
  } catch (err) {
    console.error('Revision error:', err);
    if (resultEl) resultEl.innerHTML = `<div class="error-box">${err.message}</div>`;
  }
}

function renderActionsOnly(plan) {
  const topActions = (plan.actions || []).slice(0, 3);
  const container = document.getElementById('plan-top-actions-container');
  if (!container) return;
  container.innerHTML = topActions.map((a, i) => renderActionCard(a, i + 1)).join('');
}

function renderSevenDayOnly(plan) {
  const actions = plan.actions || [];
  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const sevenDay = Array.from({ length: 7 }, () => []);
  actions.forEach(a => {
    const idx = Math.min(Math.max(a.day_index, 0), 6);
    sevenDay[idx].push(a);
  });

  const container = document.getElementById('seven-day-container');
  if (!container) return;
  container.innerHTML = sevenDay.map((dayActions, dayIdx) => `
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px">
      <div style="font-size:12px;color:var(--gold);font-weight:600;margin-bottom:6px">${dayNames[dayIdx]}</div>
      ${dayActions.length === 0 ? '<div style="font-size:11px;color:var(--text-dim)">Rest or flex</div>' : ''}
      ${dayActions.slice(0, 2).map(a => `
        <div style="font-size:11px;color:var(--text);padding:3px 0;border-bottom:1px solid var(--border)">${a.title}</div>
      `).join('')}
    </div>
  `).join('');
}

// ── Report Generation (via commercial endpoint with plan data) ──
async function generateReport() {
  if (!_currentPlanId) return;
  const previewEl = document.getElementById('report-preview');
  if (previewEl) previewEl.innerHTML = '<span class="spinner"></span> Generating full report…';

  try {
    const res = await fetch('/commercial/report/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: _sessionApiKey,
        account_name: _currentPlan?.account_name || 'unknown',
        plan_data: _currentPlanResult,
      }),
    });
    if (!res.ok) throw new Error(`Report generation failed: ${res.status}`);
    const report = await res.json();
    const s = report.summary || {};

    if (previewEl) {
      previewEl.innerHTML = `
        <div style="background:#1a2a1a;border:1px solid #3a5a3a;border-radius:8px;padding:16px;margin-top:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div style="font-size:15px;color:var(--gold);font-weight:600">📄 ${report.account_name} — Report</div>
            <button onclick="viewReportHTML('${report.report_id}')" style="background:var(--gold);border:none;border-radius:4px;color:#111;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer">View Full Report</button>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;font-size:12px">
            <div style="background:var(--bg3);padding:8px;border-radius:4px;text-align:center"><span class="dim">Value</span><br><span style="color:var(--gold);font-weight:600">${s.total_value_display || '0g'}</span></div>
            <div style="background:var(--bg3);padding:8px;border-radius:4px;text-align:center"><span class="dim">Wallet</span><br><span style="color:var(--gold);font-weight:600">${s.wallet_display || '0g'}</span></div>
            <div style="background:var(--bg3);padding:8px;border-radius:4px;text-align:center"><span class="dim">Characters</span><br><span style="color:var(--gold);font-weight:600">${s.characters || '0'}</span></div>
            <div style="background:var(--bg3);padding:8px;border-radius:4px;text-align:center"><span class="dim">Best Goal</span><br><span style="color:var(--gold);font-weight:600">${s.best_goal_progress || 0}%</span></div>
          </div>
          ${report.recommendations && report.recommendations.length > 0 ? `
            <div style="margin-top:12px;font-size:12px">
              <div class="dim" style="margin-bottom:4px">Recommendations:</div>
              <ul style="margin:0;padding-left:16px;color:var(--text)">
                ${report.recommendations.slice(0, 3).map(r => `<li style="padding:2px 0">${r}</li>`).join('')}
              </ul>
            </div>` : ''}
          <div style="margin-top:8px;font-size:11px;color:var(--text-dim)">Report #${report.report_id} · ${report.generated_at?.slice(0, 10) || ''}</div>
        </div>`;
    }

    // Also show report content on the Report page
    document.getElementById('report-empty').style.display = 'none';
    document.getElementById('report-content').style.display = 'block';
    const previewArea = document.getElementById('report-preview-area');
    if (previewArea && report.html) {
      previewArea.innerHTML = `
        <details style="margin-top:16px">
          <summary style="cursor:pointer;color:var(--gold);font-size:13px">📄 HTML Report Preview</summary>
          <div style="margin-top:8px;border:1px solid var(--border);border-radius:4px;overflow:hidden;max-height:400px;overflow-y:auto">
            <iframe srcdoc="${escapeHtml(report.html)}" style="width:100%;height:380px;border:none;background:white"></iframe>
          </div>
        </details>`;
    }

    window.viewReportHTML = (rid) => {
      window.open(`/commercial/report/html?report_id=${rid}`, '_blank');
    };
  } catch (err) {
    console.error('Report error:', err);
    if (previewEl) previewEl.innerHTML = `<div class="error-box">Failed: ${err.message}</div>`;
  }
}

// ── Pricing Card Checkout Wiring ──
function wirePricingCards() {
  document.querySelectorAll('.pricing-card button').forEach(btn => {
    btn.onclick = async () => {
      const card = btn.closest('.pricing-card');
      const isFeatured = card?.classList.contains('featured');
      const productSlug = isFeatured ? 'goal-driven-report' : 'goal-driven-weekly';

      try {
        // Get products to find the ID
        const prodRes = await fetch('/commercial/products');
        if (!prodRes.ok) throw new Error('Failed to load products');
        const prodData = await prodRes.json();
        const product = prodData.products.find(p => p.slug === productSlug);
        if (!product) throw new Error(`Product ${productSlug} not found`);

        const email = prompt('Enter your email for the report:', '');
        if (!email) return;

        btn.disabled = true;
        btn.textContent = 'Processing…';

        const checkoutRes = await fetch('/commercial/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_id: product.id,
            customer_email: email,
            account_name: _currentPlan?.account_name || '',
          }),
        });
        if (!checkoutRes.ok) throw new Error('Checkout failed');
        const checkoutData = await checkoutRes.json();
        const order = checkoutData.order;

        alert(`✅ Order complete!\n\nLicense Key: ${order.license_key}\n\nUse this key to access your report.`);

        // If we have a plan, auto-generate the report
        if (_currentPlan) {
          generateReport();
        }
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = isFeatured ? 'Purchase Report' : 'Subscribe';
      }
    };
  });
}

function wireFreeReportButton() {
  const freeBtn = document.getElementById('generate-free-report-btn');
  if (freeBtn) {
    freeBtn.onclick = () => {
      if (_currentPlan) {
        generateReport();
      } else {
        alert('Please generate a plan first on the Home page.');
      }
    };
  }
}

// ── Helpers ──
function showPage(page) {
  document.querySelectorAll('.page-section').forEach(s => s.style.display = 'none');
  const target = document.getElementById(`page-${page}`);
  if (target) target.style.display = 'block';
}

function showStatus(elId, msg, type) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = msg;
  el.className = type || '';
}

function planToText(result) {
  const plan = result.plan;
  const actions = plan.actions || [];
  let lines = [
    `GW2 Progression OS Plan`,
    `═══════════════════════════════`,
    `Account: ${plan.account_name}`,
    `Strategy: ${plan.strategy}`,
    `Estimated: ${plan.estimated_days} days`,
    `Completion: ${plan.completion_percent.toFixed(0)}%`,
    `Cost: ${fmtCoinShort(plan.total_cost_copper)}`,
    ``,
    `TOP 5 ACTIONS:`,
  ];
  actions.slice(0, 5).forEach((a, i) => {
    lines.push(`${i + 1}. ${a.title}`);
    lines.push(`   ${a.reason}`);
    if (a.reward_gold > 0) lines.push(`   Reward: +${fmtCoinShort(a.reward_gold)}`);
    if (a.cost_gold > 0) lines.push(`   Cost: ${fmtCoinShort(a.cost_gold)}`);
    lines.push(`   Time: ${a.time_cost_minutes}min`);
    lines.push(``);
  });
  lines.push(`Generated by GW2 Progression OS · ${new Date().toISOString().slice(0, 10)}`);
  return lines.join('\n');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

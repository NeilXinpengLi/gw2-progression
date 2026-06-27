// ── Plan Page — AI Decision Hub ──

import {
  itemName, itemIcon, fmtCoin, fmtCoinShort,
  resolveItems, resolveCurrencies,
} from './app-shared.js';
import { initSession, getToken } from './session-manager.js';

let _abortController = null;
let _planData = null;
let _currentStrategy = 'hybrid';

document.addEventListener('DOMContentLoaded', async () => {
  // Goal input
  const goalInput = document.getElementById('goal-input');
  document.getElementById('goal-generate-btn').addEventListener('click', generatePlan);
  goalInput.addEventListener('keydown', e => { if (e.key === 'Enter') generatePlan(); });

  // Quick goal chips
  document.querySelectorAll('.quick-goal-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      goalInput.value = btn.dataset.goal;
      generatePlan();
    });
  });

  // Strategy buttons
  document.querySelectorAll('.strategy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.strategy-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _currentStrategy = btn.dataset.strategy;
      updateStrategyDesc(_currentStrategy);
      if (_planData) regeneratePlan();
    });
  });

  // OS nav — navigate between pages
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  // Restore session
  const saved = document.getElementById('plan-account-badge');
  const token = await initSession();
  if (token && saved) {
    saved.classList.remove('hidden');
  }

  updateStrategyDesc('hybrid');
});

function updateStrategyDesc(strategy) {
  const descs = {
    hybrid: 'Balanced across gold, builds, and legendaries',
    gold: 'Maximize gold per hour — high-liquidity, high-ROI actions',
    build: 'Prioritize acquiring missing gear and completing builds',
    legendary: 'Minimize time to complete legendary weapons and gear',
  };
  document.getElementById('strategy-desc').textContent = descs[strategy] || '';
}

async function generatePlan() {
  const goalText = document.getElementById('goal-input').value.trim();

  if (_abortController) _abortController.abort();
  _abortController = new AbortController();

  showLoading(true);
  hidePlanContent();

  const apiKey = _sessionToken || document.getElementById('goal-input').value || 'demo';

  try {
    let planPayload;
    let accountName = 'Player';

    if (goalText) {
      // Goal-driven plan generation
      const interpretRes = await fetch('/goal-driven/interpret', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({goal_text: goalText}),
        signal: _abortController.signal,
      });
      if (!interpretRes.ok) throw new Error('Failed to interpret goal');

      const generateRes = await fetch('/goal-driven/generate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          api_key: apiKey,
          goal_text: goalText,
          strategy: _currentStrategy,
        }),
        signal: _abortController.signal,
      });
      if (!generateRes.ok) throw new Error('Failed to generate plan');
      planPayload = await generateRes.json();
      accountName = planPayload.plan?.account_name || 'Player';
    } else {
      // Strategy-driven plan (no goal text)
      const decideRes = await fetch('/api/v1/decide', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: apiKey, strategy: _currentStrategy}),
        signal: _abortController.signal,
      });
      if (!decideRes.ok) throw new Error('Failed to generate decisions');
      planPayload = await decideRes.json();
      accountName = planPayload.account_name || 'Player';
    }

    _planData = planPayload;
    showLoading(false);
    renderPlan(planPayload, accountName);
  } catch (e) {
    if (e.name === 'AbortError') return;
    showLoading(false);
    showPlanError(e.message);
  }
}

function regeneratePlan() {
  if (_abortController) _abortController.abort();
  _abortController = new AbortController();
  generatePlan();
}

function renderPlan(data, accountName) {
  document.getElementById('plan-account-badge').classList.remove('hidden');
  document.getElementById('plan-account-name').textContent = accountName;
  document.getElementById('plan-empty').classList.add('hidden');
  document.getElementById('plan-content').classList.remove('hidden');

  // Extract P0/P1/P2 actions
  const p0 = data.p0 || data.P0 || [];
  const p1 = data.p1 || data.P1 || [];
  const p2 = data.p2 || data.P2 || [];
  const allActions = [...p0, ...p1, ...p2];

  renderPrioritySection('plan-p0', 'P0 — Critical', '#d0a050', '#3a2a1a', p0);
  renderPrioritySection('plan-p1', 'P1 — Growth', '#6bc46b', '#1a3a2a', p1);
  renderPrioritySection('plan-p2', 'P2 — Optional', '#5a9ece', '#1a2a3a', p2);

  // Timeline
  renderTimeline();

  // Quests
  renderQuests(accountName);

  // Coach
  renderCoach(data);

  // Plan metadata
  const meta = document.getElementById('plan-meta');
  meta.innerHTML = `
    Strategy: <strong>${data.strategy_name || _currentStrategy}</strong> ·
    Account: <strong>${accountName}</strong>
  `;
}

function renderPrioritySection(containerId, title, color, bgColor, actions) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  if (!actions || actions.length === 0) {
    container.style.display = 'none';
    return;
  }
  container.style.display = 'block';

  const header = document.createElement('div');
  header.className = 'priority-header';
  header.style.background = bgColor;
  header.style.color = color;
  header.textContent = `${title} (${actions.length})`;
  container.appendChild(header);

  for (const a of actions) {
    const card = document.createElement('div');
    card.className = 'action-card';
    const reward = a.reward_copper ? fmtCoinShort(a.reward_copper) : a.reward || '';
    const score = a.final_score != null ? `score: ${(a.final_score * 100).toFixed(0)}` : '';
    card.innerHTML = `
      <span class="action-icon">${a.icon || '•'}</span>
      <span class="action-text"><strong>${escHtml(a.action || a.title || '')}</strong>: ${escHtml(a.reason || '')}</span>
      <span class="action-reward">${reward}</span>
      <span class="action-score">${score}</span>`;
    container.appendChild(card);
  }
}

function renderTimeline() {
  const grid = document.getElementById('timeline-grid');
  const days = ['Day 1','Day 2','Day 3','Day 4','Day 5','Day 6','Day 7'];
  const tasks = [
    'Sell & Liquidate',
    'Goal Progress',
    'Build Gear',
    'Map Completion',
    'Fractal Push',
    'WvW / PvP',
    'Review & Plan',
  ];
  const colors = ['#5a3a1a','#2a4a2a','#1a3a4a','#2a2a4a','#4a2a4a','#4a3a1a','#1a4a3a'];

  grid.innerHTML = days.map((day, i) => `
    <div class="timeline-day" style="background:${colors[i]};border:1px solid var(--border)">
      <div class="day-label">${day}</div>
      <div class="day-task">${tasks[i]}</div>
      <div class="day-progress"><div class="day-progress-bar" style="width:${(i + 1) * 14}%"></div></div>
    </div>`).join('');
}

async function renderQuests(accountName) {
  const list = document.getElementById('quest-list');
  try {
    const res = await fetch(`/quests/${encodeURIComponent(accountName)}`);
    if (!res.ok) return;
    const data = await res.json();
    list.innerHTML = (data.quests || []).map(q => `
      <div style="display:flex;align-items:center;gap:10px;background:var(--bg2);border:1px solid ${q.completed ? '#2a4a2a' : 'var(--border)'};border-radius:6px;padding:8px 12px;font-size:12px">
        <span style="color:${q.completed ? '#6bc46b' : 'var(--text-dim)'}">${q.completed ? '✅' : '⬜'}</span>
        <span style="flex:1">${escHtml(q.label)}</span>
      </div>`).join('');
  } catch(e) {
    list.innerHTML = '<div class="dim">Unable to load quests.</div>';
  }
}

function renderCoach(data) {
  const p0 = document.getElementById('coach-p0');
  const p1 = document.getElementById('coach-p1');
  const p2 = document.getElementById('coach-p2');
  [p0, p1, p2].forEach(el => el.innerHTML = '');

  const sections = {
    'P0 — Critical': { color: '#d0a050', bg: '#3a2a1a', items: data.coach?.P0 || [] },
    'P1 — Growth': { color: '#6bc46b', bg: '#1a3a2a', items: data.coach?.P1 || [] },
    'P2 — Optional': { color: '#5a9ece', bg: '#1a2a3a', items: data.coach?.P2 || [] },
  };

  for (const [title, info] of Object.entries(sections)) {
    if (!info.items || info.items.length === 0) continue;
    const container = info.items === (data.coach?.P0 || []) ? p0 : info.items === (data.coach?.P1 || []) ? p1 : p2;
    container.innerHTML = `
      <div class="priority-header" style="background:${info.bg};color:${info.color}">${title} (${info.items.length})</div>
      ${info.items.map((item, i) => `
        <div class="action-card" style="${i === (info.items || []).length - 1 ? 'border-radius:0 0 6px 6px' : ''}">
          <span class="action-icon">${item.icon || '•'}</span>
          <span class="action-text"><strong>${escHtml(item.action || item.title || '')}</strong>: ${escHtml(item.reason || '')}</span>
        </div>`).join('')}`;
  }
}

function showLoading(show) {
  document.getElementById('plan-loading').classList.toggle('hidden', !show);
}

function showPlanError(msg) {
  document.getElementById('plan-error-msg').textContent = msg;
  document.getElementById('plan-error').classList.remove('hidden');
}

function hidePlanContent() {
  document.getElementById('plan-content').classList.add('hidden');
  document.getElementById('plan-empty').classList.add('hidden');
  document.getElementById('plan-error').classList.add('hidden');
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>"]/g, function(m) {
    if (m === '&') return '&amp;'; if (m === '<') return '&lt;';
    if (m === '>') return '&gt;'; if (m === '"') return '&quot;';
    return m;
  });
}

window.retryPlan = function() { generatePlan(); };

import { itemName, itemIcon, fmtCoin, fmtCoinShort, resolveItems, getAccountData } from './app-shared.js';

// ── Goals ──
document.getElementById('goals-create-btn').addEventListener('click', createGoal);
document.getElementById('goals-target').addEventListener('keydown', e => { if (e.key === 'Enter') createGoal(); });

document.querySelectorAll('#nav-tabs button').forEach(btn => {
  if (btn.dataset.tab === 'goals') {
    btn.addEventListener('click', () => setTimeout(loadGoals, 100), { once: true });
  }
});

export async function loadGoals() {
  const accountName = getAccountData()?.account_name;
  if (!accountName) { document.getElementById('goals-cards').innerHTML = '<div class="dim">Run analysis first.</div>'; return; }
  try {
    const res = await fetch(`/goals?account_name=${encodeURIComponent(accountName)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const goals = await res.json();
    document.getElementById('goals-list').classList.remove('hidden');
    if (!goals.length) { document.getElementById('goals-cards').innerHTML = '<div class="dim">No goals yet. Create one above.</div>'; return; }

    const ids = [...new Set(goals.map(g => g.target_item_id))];
    await resolveItems(ids);

    document.getElementById('goals-cards').innerHTML = goals.map(g => {
      const name = itemName(g.target_item_id) || `Item #${g.target_item_id}`;
      const icon = itemIcon(g.target_item_id);
      const img = icon ? `<img src="${icon}" width="28" height="28" style="vertical-align:middle;margin-right:8px;border-radius:3px">` : '';
      const pct = g.completion_percent || 0;
      const pctColor = pct >= 100 ? '#6bc46b' : pct >= 50 ? '#d0a050' : '#c07070';
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:14px;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">${img}<div style="flex:1"><span style="color:var(--gold-light);font-weight:600">${name}</span><span class="dim"> ×${g.target_count}</span></div>
        <span class="perm-badge ${g.status==='active'?'granted':'missing'}">${g.status}</span><span style="color:var(--text-dim);font-size:11px">${g.priority}</span></div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-bottom:8px">
          <div><span class="dim" style="font-size:11px">Completion</span><br><span style="font-size:18px;font-weight:600;color:${pctColor}">${pct}%</span></div>
          <div><span class="dim" style="font-size:11px">Owned Value</span><br><span class="gold-val" style="font-size:16px">${fmtCoinShort(g.owned_material_value)}</span></div>
          <div><span class="dim" style="font-size:11px">Remaining Cost</span><br><span class="gold-val" style="font-size:16px">${fmtCoinShort(g.estimated_remaining_cost)}</span></div>
          <div><span class="dim" style="font-size:11px">Missing Items</span><br><span style="font-size:16px">${g.missing_item_count}</span></div>
        </div>
        <div style="background:var(--bg3);border-radius:3px;height:6px;overflow:hidden;margin-bottom:8px"><div style="width:${Math.min(pct,100)}%;height:100%;background:${pctColor};border-radius:3px;transition:width .5s"></div></div>
        <div style="display:flex;gap:6px">
          <button class="goal-refresh-btn" data-id="${g.goal_id}" style="background:var(--bg3);border:1px solid var(--border);border-radius:3px;color:var(--text);cursor:pointer;font-size:12px;padding:4px 12px">⟳ Refresh</button>
          <button class="goal-delete-btn" data-id="${g.goal_id}" style="background:#2a1515;border:1px solid #5a2020;border-radius:3px;color:#c07070;cursor:pointer;font-size:12px;padding:4px 12px">✕ Delete</button>
        </div></div>`;
    }).join('');

    document.querySelectorAll('.goal-refresh-btn').forEach(b => { b.addEventListener('click', () => refreshGoalUI(b.dataset.id)); });
    document.querySelectorAll('.goal-delete-btn').forEach(b => { b.addEventListener('click', () => deleteGoalUI(b.dataset.id)); });
  } catch(e) { document.getElementById('goals-cards').innerHTML = `<div class="dim">Error: ${e.message}</div>`; }
}

export async function createGoal() {
  const target = parseInt(document.getElementById('goals-target').value);
  const qty = parseInt(document.getElementById('goals-qty').value) || 1;
  const priority = document.getElementById('goals-priority').value;
  const key = document.getElementById('key-input').value.trim();
  if (!key) { setGoalsStatus('error','Enter API key first.'); return; }
  if (!target) { setGoalsStatus('error','Enter a target item ID.'); return; }
  setGoalsStatus('', '<span class="spinner"></span> Creating goal…');
  try {
    const res = await fetch('/goals', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ api_key:key, target_item_id:target, target_count:qty, priority }) });
    if (!res.ok) throw new Error(((await res.json()).detail || `HTTP ${res.status}`));
    setGoalsStatus('ok', 'Goal created!');
    document.getElementById('goals-target').value = '';
    loadGoals();
  } catch(e) { setGoalsStatus('error', `Error: ${e.message}`); }
}

export async function refreshGoalUI(goalId) {
  const key = document.getElementById('key-input').value.trim();
  if (!key) return;
  setGoalsStatus('', '<span class="spinner"></span> Refreshing…');
  try {
    const res = await fetch(`/goals/${goalId}/refresh`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ api_key:key }) });
    if (!res.ok) throw new Error(((await res.json()).detail || `HTTP ${res.status}`));
    setGoalsStatus('ok', 'Goal refreshed!'); loadGoals();
  } catch(e) { setGoalsStatus('error', `Error: ${e.message}`); }
}

export async function deleteGoalUI(goalId) {
  try {
    const res = await fetch(`/goals/${goalId}`, { method:'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`); loadGoals();
  } catch(e) { setGoalsStatus('error', `Error: ${e.message}`); }
}

export function setGoalsStatus(cls, msg) {
  const el = document.getElementById('goals-status');
  el.className = cls === 'error' ? 'error' : ''; el.innerHTML = msg;
}

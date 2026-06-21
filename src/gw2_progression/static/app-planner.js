// ── Planner Tab ──
document.getElementById('planner-btn').addEventListener('click', runPlanner);
loadTemplates();

async function loadTemplates() {
  try {
    const res = await fetch('/progression/templates');
    if (!res.ok) return;
    const templates = await res.json();
    const sel = document.getElementById('planner-template');
    sel.innerHTML = templates.map(t => `<option value="${t.template_id}">${t.name} (${t.goal_type})</option>`).join('');
  } catch(e) { /* ignore */ }
}

async function runPlanner() {
  const templateId = document.getElementById('planner-template').value;
  const key = document.getElementById('key-input').value.trim();
  if (!key) { setPlannerStatus('error','Enter API key.'); return; }
  setPlannerStatus('', '<span class="spinner"></span> Generating plan…');
  try {
    const res = await fetch('/progression/plans', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ api_key:key, template_id:templateId }) });
    if (!res.ok) throw new Error(((await res.json()).detail||`HTTP ${res.status}`));
    const plan = await res.json();
    document.getElementById('planner-plan').classList.remove('hidden');
    document.getElementById('planner-summary').innerHTML = `
      <div class="value-card"><div class="vc-label">Completion</div><div class="vc-value" style="color:${plan.total_completion_percent>=80?'#6bc46b':plan.total_completion_percent>=40?'#d0a050':'#c07070'}">${plan.total_completion_percent}%</div></div>
      <div class="value-card"><div class="vc-label">Missing Cost</div><div class="vc-value gold-val">${fmtCoinShort(plan.total_missing_cost)}</div></div>
      <div class="value-card"><div class="vc-label">Owned Value</div><div class="vc-value gold-val">${fmtCoinShort(plan.total_owned_material_value)}</div></div>
      <div class="value-card"><div class="vc-label">Blocked</div><div class="vc-value">${plan.blocked_requirement_count}</div></div>`;
    const reqs = document.getElementById('planner-requirements');
    reqs.innerHTML = '<table class="data-table"><thead><tr><th>Requirement</th><th>Type</th><th>Owned</th><th>Required</th><th>Status</th></tr></thead><tbody>' +
      (plan.requirements||[]).map(r => `<tr><td class="gold-val">${r.ref_name||`#${r.ref_id}`}</td><td class="dim">${r.requirement_type}</td><td>${r.owned_count}</td><td>${r.required_count}</td><td><span class="perm-badge ${r.status==='complete'?'granted':'missing'}">${r.status}</span></td></tr>`).join('') + '</tbody></table>';
    setPlannerStatus('ok', 'Plan generated.');
  } catch(e) { setPlannerStatus('error', `Error: ${e.message}`); }
}

function setPlannerStatus(cls, msg) { const el=document.getElementById('planner-status'); el.className=cls==='error'?'error':''; el.innerHTML=msg; }

// ── Builds Tab ──
document.getElementById('builds-btn').addEventListener('click', runBuilds);

async function runBuilds() {
  const key = document.getElementById('key-input').value.trim();
  if (!key) { setBuildsStatus('error','Enter API key.'); return; }
  setBuildsStatus('', '<span class="spinner"></span> Analyzing builds…');
  try {
    const res = await fetch('/builds/recommendations', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ api_key:key }) });
    if (!res.ok) throw new Error(((await res.json()).detail||`HTTP ${res.status}`));
    const recs = await res.json();
    document.getElementById('builds-results').classList.remove('hidden');
    const ids = [...new Set(recs.map(r=>r.build_id))];
    document.getElementById('builds-results').innerHTML = recs.length ? recs.map(r => {
      const pctColor = r.readiness_score>=0.7?'#6bc46b':r.readiness_score>=0.4?'#d0a050':'#c07070';
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:14px;margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="color:var(--gold-light);font-weight:600">${r.build_name}</span>
          <span class="perm-badge ${r.profession_match?'granted':'missing'}">${r.profession_match?'✓ Prof Match':'✗ No Match'}</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px">
          <div><span class="dim" style="font-size:11px">Readiness</span><br><span style="font-size:22px;font-weight:600;color:${pctColor}">${(r.readiness_score*100).toFixed(0)}%</span></div>
          <div><span class="dim" style="font-size:11px">Gear</span><br><span style="font-size:16px">${r.gear_completion_percent}%</span></div>
          <div><span class="dim" style="font-size:11px">Missing Items</span><br><span style="font-size:16px">${r.missing_items_count}</span></div>
          <div><span class="dim" style="font-size:11px">Est. Cost</span><br><span class="gold-val" style="font-size:16px">${fmtCoinShort(r.missing_cost)}</span></div>
        </div></div>`;
    }).join('') : '<div class="dim">No builds available for your account.</div>';
    setBuildsStatus('ok', `Found ${recs.length} build(s).`);
  } catch(e) { setBuildsStatus('error', `Error: ${e.message}`); }
}

function setBuildsStatus(cls, msg) { const el=document.getElementById('builds-status'); el.className=cls==='error'?'error':''; el.innerHTML=msg; }

// ── Market Tab ──
document.getElementById('market-btn').addEventListener('click', runMarket);

async function runMarket() {
  const accountName = _accountData?.account_name;
  if (!accountName) { setMarketStatus('error','Run analysis first.'); return; }
  setMarketStatus('', '<span class="spinner"></span> Analyzing market signals…');
  try {
    const res = await fetch(`/tp/signals?account_name=${encodeURIComponent(accountName)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const signals = await res.json();
    document.getElementById('market-results').classList.remove('hidden');
    const sell = signals.filter(s=>s.signal_type==='sell_candidate');
    const buy = signals.filter(s=>s.signal_type==='buy_candidate');
    const warnings = signals.filter(s=>s.severity==='warning');
    const ids=[...new Set(signals.map(s=>s.item_id).filter(Boolean))];
    if (ids.length) await resolveItems(ids);

    document.getElementById('market-sell').innerHTML = sell.length ? sell.map(s => `<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;font-size:13px"><span>${itemName(s.item_id)}</span><span class="gold-val">×${s.quantity_owned} = ${fmtCoinShort(s.value_owned)}</span></div>`).join('') : '<div class="dim">No sell candidates.</div>';
    document.getElementById('market-buy').innerHTML = buy.length ? buy.map(s => `<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;font-size:13px"><span>${itemName(s.item_id)}</span><span class="gold-val">${fmtCoinShort(s.current_sell_price)}</span></div>`).join('') : '<div class="dim">No buy opportunities.</div>';
    document.getElementById('market-warnings').innerHTML = warnings.length ? warnings.map(w => `<div class="error-box" style="margin-top:4px;padding:8px 12px;font-size:13px"><strong>⚠ ${w.signal_type}</strong>: ${w.reason} ${w.item_id?'(Item #'+w.item_id+')':''}</div>`).join('') : '<div class="dim">No warnings.</div>';
    setMarketStatus('ok', `Found ${signals.length} signal(s).`);
  } catch(e) { setMarketStatus('error', `Error: ${e.message}`); }
}

function setMarketStatus(cls, msg) { const el=document.getElementById('market-status'); el.className=cls==='error'?'error':''; el.innerHTML=msg; }

// ── Advisor Tab ──
document.getElementById('advisor-btn').addEventListener('click', runAdvisor);

async function runAdvisor() {
  const key = document.getElementById('key-input').value.trim();
  if (!key) { setAdvisorStatus('error','Enter API key.'); return; }
  setAdvisorStatus('', '<span class="spinner"></span> Generating advice…');
  try {
    const res = await fetch('/agent/progression/advice', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ api_key:key }) });
    if (!res.ok) throw new Error(((await res.json()).detail||`HTTP ${res.status}`));
    const advice = await res.json();
    document.getElementById('advisor-results').classList.remove('hidden');
    document.getElementById('advisor-actions').innerHTML = (advice.recommended_actions||[]).length ?
      (advice.recommended_actions||[]).map(a => `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px"><div style="font-weight:600;color:var(--gold-light)">${a.action}</div><div style="font-size:13px;color:var(--text-dim);margin-top:4px">${a.reason}</div></div>`).join('') :
      '<div class="dim">No actions recommended.</div>';
    document.getElementById('advisor-weekly').innerHTML = (advice.weekly_plan||[]).length ?
      '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px">' + (advice.weekly_plan||[]).map(d => `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px"><div style="font-weight:600;color:var(--gold);margin-bottom:6px">${d.day}</div>${(d.tasks||[]).map(t => `<div style="font-size:12px;color:var(--text-dim);padding:2px 0">• ${t}</div>`).join('')}</div>`).join('') + '</div>' :
      '<div class="dim">No weekly plan.</div>';
    setAdvisorStatus('ok', 'Advice generated.');
  } catch(e) { setAdvisorStatus('error', `Error: ${e.message}`); }
}

function setAdvisorStatus(cls, msg) { const el=document.getElementById('advisor-status'); el.className=cls==='error'?'error':''; el.innerHTML=msg; }

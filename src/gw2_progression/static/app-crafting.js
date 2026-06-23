import { itemName, itemIcon, fmtCoin, fmtCoinShort, resolveItems, resolveSearch } from './app-shared.js';

// ── Crafting Calculator ──
document.getElementById('craft-btn').addEventListener('click', runCrafting);
document.getElementById('craft-target').addEventListener('keydown', e => { if (e.key === 'Enter') runCrafting(); });

let _craftSearchTimer = null;
document.getElementById('craft-search').addEventListener('input', () => {
  clearTimeout(_craftSearchTimer);
  const q = document.getElementById('craft-search').value.trim();
  if (q.length < 2) { document.getElementById('craft-search-results').classList.add('hidden'); return; }
  _craftSearchTimer = setTimeout(() => doCraftSearch(q), 300);
});
document.addEventListener('click', e => {
  const dd = document.getElementById('craft-search-results');
  if (!e.target.closest('#craft-search') && !e.target.closest('.craft-search-dropdown')) dd.classList.add('hidden');
});

export async function doCraftSearch(query) {
  const dd = document.getElementById('craft-search-results');
  try {
    const ids = await resolveSearch(query);
    if (!ids || !ids.length) { dd.innerHTML = '<div class="craft-search-item dim">No results</div>'; dd.classList.remove('hidden'); return; }
    await resolveItems(ids.slice(0, 20));
    dd.innerHTML = ids.slice(0, 15).map(id => {
      const ic = itemIcon(id); const im = ic ? `<img src="${ic}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">` : '';
      return `<div class="craft-search-item" data-id="${id}">${im}${itemName(id)} <span class="dim">(#${id})</span></div>`;
    }).join('');
    dd.classList.remove('hidden');
    dd.querySelectorAll('.craft-search-item').forEach(el => {
      el.addEventListener('click', () => {
        document.getElementById('craft-target').value = el.dataset.id;
        document.getElementById('craft-search').value = el.textContent.trim().split(' (#')[0];
        dd.classList.add('hidden');
      });
    });
  } catch(e) { dd.innerHTML = '<div class="craft-search-item dim">Search failed</div>'; dd.classList.remove('hidden'); }
}

export async function runCrafting() {
  const target = parseInt(document.getElementById('craft-target').value);
  const qty = parseInt(document.getElementById('craft-qty').value) || 1;
  const useOwned = document.getElementById('craft-use-owned').checked;
  const key = document.getElementById('key-input').value.trim();
  if (!key) { setCraftStatus('error','Enter API key first.'); return; }
  if (!target || target < 1) { setCraftStatus('error','Enter a valid target item ID.'); return; }

  const btn = document.getElementById('craft-btn');
  btn.disabled = true;
  setCraftStatus('', '<span class="spinner"></span> Fetching account data…');
  resolveItems([target]);
  setCraftStatus('', '<span class="spinner"></span> Fetching recipe tree & prices…');
  document.getElementById('craft-results').classList.add('hidden');

  try {
    const res = await fetch('/crafting/calculate', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ api_key:key, target_item_id:target, quantity:qty, use_owned:useOwned }),
    });
    if (!res.ok) throw new Error(((await res.json().catch(()=>({}))).detail || `HTTP ${res.status}`));
    const data = await res.json();

    const allIds = new Set([target]);
    for (const item of (data.missing_items||[])) { if (item.item_id) allIds.add(item.item_id); }
    for (const item of (data.shopping_list||[])) { if (item.item_id) allIds.add(item.item_id); }
    for (const step of (data.crafting_steps||[])) { if (step.item_id) allIds.add(step.item_id); }
    for (const alt of (data.alternative_recipes||[])) { for (const ing of (alt.ingredients||[])) { if (ing.item_id) allIds.add(ing.item_id); } }
    setCraftStatus('', '<span class="spinner"></span> Resolving item names…');
    await resolveItems([...allIds]);
    setCraftStatus('ok', 'Calculation complete.');
    renderCraftingResults(data);
  } catch(e) { setCraftStatus('error', `Error: ${e.message}`); }
  finally { btn.disabled = false; }
}

export function setCraftStatus(cls, msg) {
  const el = document.getElementById('craft-status');
  el.className = cls === 'error' ? 'error' : ''; el.innerHTML = msg;
}

export function renderCraftingResults(data) {
  const container = document.getElementById('craft-results');
  container.classList.remove('hidden');
  const targetName = itemName(data.target_item_id) || `Item #${data.target_item_id}`;
  document.getElementById('craft-target-name').textContent = `${targetName} × ${data.target_count}`;
  document.getElementById('craft-buy-cost').textContent = fmtCoin(data.total_buy_cost);
  document.getElementById('craft-craft-cost').textContent = fmtCoin(data.total_craft_cost);
  document.getElementById('craft-owned-used').textContent = fmtCoin((data.owned_used||0) * 10000) || '0g';

  const shopping = document.getElementById('craft-shopping');
  const sl = data.shopping_list || [];
  if (sl.length) {
    shopping.innerHTML = '<table class="data-table"><thead><tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead><tbody>' +
      sl.map(item => { const ic = itemIcon(item.item_id); const im = ic ? `<img src="${ic}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : ''; return `<tr><td>${im}${itemName(item.item_id)}</td><td>${item.count.toLocaleString()}</td><td class="gold-val">${fmtCoinShort(item.unit_price)}</td><td class="gold-val">${fmtCoinShort(item.total)}</td></tr>`; }).join('') + '</tbody></table>';
  } else { shopping.innerHTML = '<div class="dim">Nothing to buy — all materials are owned!</div>'; }

  const steps = document.getElementById('craft-steps');
  const cs = data.crafting_steps || [];
  if (cs.length) {
    steps.innerHTML = '<div style="display:flex;flex-direction:column;gap:4px">' + cs.map(s => {
      const indent = s.depth * 16;
      const ic = itemIcon(s.item_id); const im = ic ? `<img src="${ic}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">` : '';
      return `<div style="margin-left:${indent}px;padding:6px 10px;background:var(--bg2);border:1px solid var(--border);border-radius:3px;display:flex;align-items:center;gap:8px">${im}<span style="flex:1">${itemName(s.item_id)} × ${s.count.toLocaleString()}</span><span class="${s.missing>0?'gold-val':'dim'}">Owned: ${s.owned} | Missing: ${s.missing}</span><span class="gold-val">${fmtCoinShort(s.buy_cost)}</span></div>`;
    }).join('') + '</div>';
  } else { steps.innerHTML = '<div class="dim">No crafting steps needed.</div>'; }

  const missing = document.getElementById('craft-missing-detail');
  const mi = data.missing_items || [];
  if (mi.length) {
    missing.innerHTML = '<table class="data-table"><thead><tr><th>Item</th><th>Needed</th><th>Owned</th><th>Missing</th><th>Unit Price</th><th>Total Cost</th></tr></thead><tbody>' +
      mi.map(item => { const ic = itemIcon(item.item_id); const im = ic ? `<img src="${ic}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : ''; return `<tr><td>${im}${itemName(item.item_id)}</td><td>${item.needed.toLocaleString()}</td><td>${item.owned.toLocaleString()}</td><td class="gold-val">${item.missing.toLocaleString()}</td><td>${fmtCoinShort(item.buy_unit_price)}</td><td class="gold-val">${fmtCoinShort(item.total_cost)}</td></tr>`; }).join('') + '</tbody></table>';
  } else { missing.innerHTML = '<div class="dim">No missing materials.</div>'; }

  const altC = document.getElementById('craft-alternatives');
  const alts = data.alternative_recipes || [];
  if (alts.length) {
    altC.innerHTML = '<div style="display:flex;flex-direction:column;gap:8px">' + alts.map(alt => {
      const ings = (alt.ingredients||[]).map(ing => { const ic = itemIcon(ing.item_id); const im = ic ? `<img src="${ic}" width="16" height="16" style="vertical-align:middle;margin-right:3px;border-radius:2px">` : ''; return `${im}${itemName(ing.item_id)} ×${ing.count}`; }).join(', ');
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:10px 14px;font-size:13px"><span style="color:var(--gold)">Recipe #${alt.recipe_id}</span><span class="dim"> — ${(alt.disciplines||[]).join(', ')} (Rating ${alt.min_rating})</span><div style="margin-top:4px;color:var(--text-dim)">${ings}</div></div>`;
    }).join('') + '</div>';
  } else { altC.innerHTML = '<div class="dim">No alternative recipes found.</div>'; }
}

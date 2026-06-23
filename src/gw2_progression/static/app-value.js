import { _itemCache, _matCatCache,
  getValueCharts, setValueCharts,
  resolveMatCategories, itemName, itemIcon, fmtCoin, fmtCoinShort, colorHex,
  getAccountData,
} from './app-shared.js';



// ── Value Dashboard ──
export function renderValue(vd) {
  Object.values(getValueCharts()).forEach(c => { try { c.destroy(); } catch(e) {} });
  setValueCharts({ _rendered: false });

  const errEl = document.getElementById('err-value');
  if (!vd) {
    errEl.innerHTML = '<div class="error-box">Value analysis unavailable. Ensure your API key has the appropriate permissions (inventories, tradingpost).</div>';
    document.getElementById('value-summary-cards').innerHTML = '';
    document.querySelector('#value-top-table tbody').innerHTML = '<tr><td colspan="7" class="dim">No value data</td></tr>';
    document.getElementById('value-warnings').innerHTML = '';
    return;
  }
  errEl.innerHTML = '';
  const s = vd.summary;
  const hist = vd.history || [];
  const prev = hist.length > 1 ? hist[1] : null;
  const vsP = (cur, prv) => prv === undefined || prv === null ? '' : (cur === prv ? '' : `<span class="${cur > prv ? 'vs-up' : 'vs-down'}">${cur > prv ? '▲' : '▼'} ${fmtCoinShort(Math.abs(cur - prv))}</span>`);

  document.getElementById('value-summary-cards').innerHTML = `
    <div class="stat-card"><div class="label">Total Estimated Value</div><div class="value">${fmtCoin(s.total_value_buy)}</div><div class="sub">based on highest buy orders ${vsP(s.total_value_buy, prev?.total_value_buy)}</div></div>
    <div class="stat-card"><div class="label">Wallet Gold</div><div class="value">${fmtCoin(s.wallet_value)}</div><div class="sub">liquid gold ${vsP(s.wallet_value, prev?.wallet_value)}</div></div>
    <div class="stat-card"><div class="label">Reliable Value</div><div class="value" style="color:#6bc46b">${fmtCoinShort(s.reliable_value)}</div><div class="sub">high liquidity & fair spread</div></div>
    <div class="stat-card"><div class="label">Risky Value</div><div class="value" style="color:#d0a050">${fmtCoinShort(s.risky_value)}</div><div class="sub">low liquidity or wide spread</div></div>
    <div class="stat-card"><div class="label">Materials (Buy)</div><div class="value">${fmtCoinShort(s.material_value_buy)}</div><div class="sub">material storage value ${vsP(s.material_value_buy, prev?.material_value)}</div></div>
    <div class="stat-card"><div class="label">Bank (Buy)</div><div class="value">${fmtCoinShort(s.bank_value_buy)}</div><div class="sub">bank inventory value ${vsP(s.bank_value_buy, prev?.bank_value)}</div></div>
    <div class="stat-card"><div class="label">Characters (Buy)</div><div class="value">${fmtCoinShort(s.character_inventory_value_buy)}</div><div class="sub">character inventory value ${vsP(s.character_inventory_value_buy, prev?.inventory_value)}</div></div>
    <div class="stat-card"><div class="label">TP Orders</div><div class="value">${fmtCoinShort(s.tradingpost_value)}</div><div class="sub">buy ${fmtCoinShort(s.tradingpost_buy_value)} | sell ${fmtCoinShort(s.tradingpost_sell_value)} ${vsP(s.tradingpost_value, prev?.tradingpost_value)}</div></div>
  `.trim();

  document.getElementById('vc-instant').textContent = fmtCoin(s.total_value_buy);
  document.getElementById('vc-listing').textContent = fmtCoin(s.total_value_sell);
  document.getElementById('vc-net').textContent = fmtCoin(s.net_sell_value);
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
      const locLabels = { material_storage: 'Material Storage', bank: 'Bank', character: 'Character', shared_inventory: 'Shared Inv', tradingpost: 'TP Orders', wallet: 'Wallet' };
      const loc = locLabels[item.location_type] || item.location_type;
      const qMap = { reliable: '', low_liquidity: '⚠️', illiquid: '⚠️', wide_spread: '📊', missing_buy: '❓' };
      const qIcon = item.quality_status ? qMap[item.quality_status] || '' : '';
      let sEl = `<span class="perm-badge granted">Priced</span>`;
      if (item.valuation_status === 'unpriced') sEl = `<span class="perm-badge missing">Unpriced</span>`;
      if (item.valuation_status === 'account_bound') sEl = `<span class="perm-badge missing">Bound</span>`;
      return `<tr><td>${i+1}</td><td>${img}<span class="gold-val">${name}</span> ${qIcon}</td><td class="dim">${loc}${item.location_ref ? ' ('+item.location_ref.slice(0,20)+')' : ''}</td><td>${item.count.toLocaleString()}</td><td class="gold-val">${fmtCoinShort(item.value_buy)}</td><td class="gold-val">${fmtCoinShort(item.value_sell)}</td><td>${sEl}</td></tr>`;
    }).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="7" class="dim">No items with value data</td></tr>';
  }

  // Materials by Category
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
  const matCatIds = Object.keys(matByCat).filter(c => c !== '0').map(Number);
  if (matCatIds.length) resolveMatCategories();
  renderMaterialsGrid(matByCat);

  // All Holdings
  window._allHoldings = vd.holdings || [];
  window._holdingsPage = 0;
  window._holdingsPageSize = 50;
  document.getElementById('holdings-count').textContent = (_allHoldings.length || 0).toLocaleString();
  renderHoldingsPage();
  document.getElementById('holdings-count-display').textContent = `${_allHoldings.length || 0} items total`;

  // Warnings
  const warningsEl = document.getElementById('value-warnings');
  const warnings = vd.warnings || [];
  if (warnings.length) {
    warningsEl.innerHTML = warnings.map(w => {
      const icons = { missing_permissions: '⚠️', account_bound: '🔒', unpriced: '❓', no_price: '❓' };
      return `<div class="error-box" style="margin-top:4px;padding:8px 12px;font-size:13px"><strong>${icons[w.warning_type] || 'ℹ'} ${w.warning_type}</strong>: ${w.message}${w.item_id ? ' (Item #'+w.item_id+')' : ''}</div>`;
    }).join('');
  } else {
    warningsEl.innerHTML = '<div class="dim" style="padding:8px 0">No valuation warnings.</div>';
  }

  // History
  const histC = document.getElementById('history-chart-container');
  const histE = document.getElementById('value-history-empty');
  if (hist.length > 1) { histC.style.display = 'block'; histE.style.display = 'none'; }
  else if (hist.length === 1) { histC.style.display = 'none'; histE.textContent = 'Only one snapshot recorded. Run valuation again to build history.'; histE.style.display = 'block'; }
  else { histC.style.display = 'none'; histE.style.display = 'block'; }

  ['value-pie-chart','value-bar-chart','value-line-chart'].forEach(id => {
    const c = document.getElementById(id);
    if (c) { const e = Chart.getChart(c); if (e) e.destroy(); }
  });
  getValueCharts()._rendered = false;
  const vb = document.querySelector('button[data-tab="value"]');
  if (vb && vb.classList.contains('active')) renderValueCharts(vd);
}

export function renderValueCharts(vd) {
  if (!vd) return;
  getValueCharts()._rendered = true;
  const textColor = '#888'; const darkGrid = '#333';
  const COLORS = ['#c8956c','#5a9e5a','#5080a0','#a05050','#b080d0','#d0b050'];
  const COLORS_A = ['rgba(200,149,108,0.8)','rgba(90,158,90,0.8)','rgba(80,128,160,0.8)','rgba(160,80,80,0.8)','rgba(176,128,208,0.8)','rgba(208,176,80,0.8)'];
  const breakdown = vd.breakdown?.by_location || [];

  const pieC = document.getElementById('value-pie-chart');
  if (pieC && breakdown.length) {
    const pd = breakdown.filter(b => b.value_buy > 0);
    new Chart(pieC, { type:'doughnut', data:{ labels:pd.map(b=>b.label), datasets:[{ data:pd.map(b=>b.value_buy), backgroundColor:COLORS.slice(0,pd.length), borderColor:'#0f0f0f', borderWidth:2 }] },
      options:{ responsive:true, maintainAspectRatio:true, plugins:{ legend:{ position:'right', labels:{ color:textColor, padding:12, font:{size:11}, generateLabels:function(chart){ return chart.data.labels.map((l,i)=>({text:`${l}: ${fmtCoinShort(chart.data.datasets[0].data[i])}`, fillStyle:chart.data.datasets[0].backgroundColor[i], strokeStyle:'#333', index:i })); }}}, tooltip:{ backgroundColor:'#111', borderColor:'#333', borderWidth:1, titleColor:'#eee', bodyColor:'#ccc', callbacks:{ label:ctx=>` ${ctx.label}: ${fmtCoin(ctx.parsed)}` } }} } });
  }

  const barC = document.getElementById('value-bar-chart');
  if (barC && breakdown.length) {
    const s = [...breakdown].sort((a,b)=>b.value_buy-a.value_buy);
    new Chart(barC, { type:'bar', data:{ labels:s.map(b=>b.label), datasets:[{ label:'Buy Value', data:s.map(b=>b.value_buy), backgroundColor:COLORS_A, borderColor:COLORS, borderWidth:1, borderRadius:3 }] },
      options:{ responsive:true, maintainAspectRatio:true, indexAxis:'y', plugins:{ legend:{display:false}, tooltip:{ backgroundColor:'#111', borderColor:'#333', borderWidth:1, titleColor:'#eee', bodyColor:'#ccc', callbacks:{label:ctx=>` ${fmtCoin(ctx.parsed.x)}`}} }, scales:{ x:{ ticks:{ color:textColor, font:{size:10}, callback:v=>fmtCoinShort(v)}, grid:{color:darkGrid} }, y:{ ticks:{color:textColor, font:{size:11}}, grid:{display:false} }} } });
  }

  const lineC = document.getElementById('value-line-chart');
  const h = vd.history || [];
  if (lineC && h.length > 1) {
    const sh = [...h].reverse();
    new Chart(lineC, { type:'line', data:{ labels:sh.map(x=>x.snapshot_time?x.snapshot_time.slice(5,16).replace('T',' '):''), datasets:[
      { label:'Total Value (Buy)', data:sh.map(x=>x.total_value_buy), borderColor:'#c8956c', backgroundColor:'rgba(200,149,108,0.1)', fill:true, tension:0.3, pointRadius:3 },
      { label:'Total Value (Sell)', data:sh.map(x=>x.total_value_sell), borderColor:'#5a9e5a', fill:false, tension:0.3, pointRadius:3, borderDash:[4,4] }
    ]}, options:{ responsive:true, maintainAspectRatio:true, interaction:{ intersect:false, mode:'index' }, plugins:{ legend:{ position:'top', labels:{color:textColor, font:{size:11}, padding:16}}, tooltip:{ backgroundColor:'#111', borderColor:'#333', borderWidth:1, titleColor:'#eee', bodyColor:'#ccc', callbacks:{label:ctx=>` ${ctx.dataset.label}: ${fmtCoin(ctx.parsed.y)}`}} }, scales:{ x:{ ticks:{color:textColor, font:{size:10}, maxTicksLimit:10}, grid:{color:darkGrid} }, y:{ ticks:{color:textColor, font:{size:10}, callback:v=>fmtCoinShort(v)}, grid:{color:darkGrid} }} } });
  }
}

export function renderMaterialsGrid(matByCat) {
  const grid = document.getElementById('materials-grid');
  const entries = Object.entries(matByCat).sort((a,b)=>b[1].total_buy-a[1].total_buy);
  if (!entries.length) { grid.innerHTML = '<div class="dim">No material storage data.</div>'; return; }
  grid.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px">' +
    entries.map(([cat,data]) => {
      const catName = _matCatCache[cat] || `Category ${cat}`;
      const top = [...data.items].sort((a,b)=>b.value_buy-a.value_buy).slice(0,5);
      const topItems = top.map(h => {
        const ic = itemIcon(h.item_id);
        const im = ic ? `<img src="${ic}" width="16" height="16" style="vertical-align:middle;margin-right:3px;border-radius:2px">` : '';
        return `<div style="font-size:11px;color:var(--text-dim);display:flex;align-items:center;gap:4px">${im}<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${itemName(h.item_id)}</span><span class="gold-val">${fmtCoinShort(h.value_buy)}</span></div>`;
      }).join('');
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px"><div style="font-size:12px;color:var(--gold);font-weight:600;margin-bottom:6px">${catName}</div><div style="font-size:18px;font-weight:600;color:var(--gold-light);margin-bottom:6px">${fmtCoinShort(data.total_buy)}</div><div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">${data.items.length} items</div>${topItems}</div>`;
    }).join('') + '</div>';
}

export function toggleMaterials() {
  const section = document.getElementById('materials-section');
  const title = section.previousElementSibling;
  const isHidden = section.style.display === 'none';
  section.style.display = isHidden ? 'block' : 'none';
  if (title) { const s = title.querySelector('span'); if (s) s.innerHTML = (isHidden ? '▼' : '▶') + ' Materials by Category'; }
}

function renderHoldingsPage() {
  const data = window._allHoldings || [];
  let page = window._holdingsPage || 0;
  const ps = window._holdingsPageSize || 50;
  const q = document.getElementById('holdings-search').value.trim().toLowerCase();
  const loc = document.getElementById('holdings-location').value;
  const status = document.getElementById('holdings-status').value;

  const filtered = data.filter(h => { if (q) return String(h.item_id).includes(q); return true; }).filter(h => { if (loc) return h.location_type === loc; return true; }).filter(h => { if (status) return h.valuation_status === status; return true; });
  const totalFiltered = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / ps));
  page = Math.min(page, totalPages - 1);
  const start = page * ps;
  const pageItems = filtered.slice(start, start + ps);

  const tbody = document.querySelector('#holdings-table tbody');
  if (!pageItems.length) { tbody.innerHTML = '<tr><td colspan="6" class="dim">No matching items</td></tr>'; }
  else {
    tbody.innerHTML = pageItems.map(h => {
      const name = itemName(h.item_id);
      const icon = itemIcon(h.item_id);
      const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
      const locLabels = { material_storage:'Mat Storage', bank:'Bank', shared_inventory:'Shared', tradingpost:'TP', wallet:'Wallet' };
      let locDisplay = locLabels[h.location_type] || h.location_type;
      if (h.location_type === 'character' && h.location_ref) locDisplay = 'Char: ' + h.location_ref.split('/')[0];
      let sEl = `<span class="perm-badge granted">Priced</span>`;
      if (h.valuation_status === 'unpriced') sEl = `<span class="perm-badge missing">Unpriced</span>`;
      if (h.valuation_status === 'account_bound') sEl = `<span class="perm-badge missing">Bound</span>`;
      return `<tr data-item="${h.item_id}" data-loc="${h.location_type}" data-status="${h.valuation_status}"><td>${img}<span class="gold-val">${name}</span></td><td>${h.count.toLocaleString()}</td><td class="dim">${locDisplay}</td><td class="gold-val">${h.value_buy ? fmtCoinShort(h.value_buy) : '—'}</td><td class="gold-val">${h.value_sell ? fmtCoinShort(h.value_sell) : '—'}</td><td>${sEl}</td></tr>`;
    }).join('');
  }

  document.getElementById('holdings-count-display').textContent = `${totalFiltered} items total (page ${page+1}/${totalPages})`;
  const pagination = document.getElementById('holdings-pagination');
  if (totalPages <= 1) { pagination.innerHTML = ''; return; }
  let html = '<div style="display:flex;gap:6px;align-items:center;padding:10px 0;flex-wrap:wrap">';
  if (page > 0) html += `<button class="page-btn" data-page="0">«</button><button class="page-btn" data-page="${page-1}">‹</button>`;
  for (let p = Math.max(0, page-2); p <= Math.min(totalPages-1, page+2); p++) html += `<button class="page-btn${p===page?' page-active':''}" data-page="${p}">${p+1}</button>`;
  if (page < totalPages-1) html += `<button class="page-btn" data-page="${page+1}">›</button><button class="page-btn" data-page="${totalPages-1}">»</button>`;
  html += '</div>';
  pagination.innerHTML = html;
  pagination.querySelectorAll('.page-btn').forEach(btn => { btn.addEventListener('click', () => { window._holdingsPage = parseInt(btn.dataset.page); renderHoldingsPage(); }); });
}

export function filterHoldings() { window._holdingsPage = 0; renderHoldingsPage(); }

function toggleHoldings() {
  const section = document.getElementById('holdings-section');
  const title = section.previousElementSibling;
  const isHidden = section.style.display === 'none';
  section.style.display = isHidden ? 'block' : 'none';
  if (title) { const s = title.querySelector('span'); if (s) s.innerHTML = (isHidden ? '▼' : '▶') + s.innerHTML.slice(1); }
}

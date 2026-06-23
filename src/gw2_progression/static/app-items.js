import { itemName, itemIcon, fmtCoin, fmtCoinShort, resolveItems, getAccountData } from './app-shared.js';

// ── Items Tab ──
document.getElementById('items-search-btn').addEventListener('click', runItemsSearch);
document.getElementById('items-search-input').addEventListener('keydown', e => { if (e.key === 'Enter') runItemsSearch(); });
document.getElementById('items-search-input').addEventListener('input', () => {
  clearTimeout(_itemsSearchTimer);
  _itemsSearchTimer = setTimeout(() => {
    if (document.getElementById('items-search-input').value.trim().length >= 2) runItemsSearch();
  }, 400);
});
document.getElementById('items-detail-back').addEventListener('click', () => {
  document.getElementById('items-detail').classList.add('hidden');
  document.getElementById('items-results-table').classList.remove('hidden');
});
document.querySelectorAll('.quick-filter-btn').forEach(btn => {
  btn.addEventListener('click', () => runItemsFilter(btn.dataset.filter));
});

export async function runItemsSearch() {
  const q = document.getElementById('items-search-input').value.trim();
  const loc = document.getElementById('items-location-filter').value;
  const status = document.getElementById('items-status-filter').value;
  const accountName = getAccountData()?.account_name;
  if (!accountName) { setItemsStatus('error', 'Run analysis first (Overview tab).'); return; }
  if (!q) { setItemsStatus('error', 'Enter an item name or ID.'); return; }
  setItemsStatus('', '<span class="spinner"></span> Searching…');
  await _doItemsFetch(`/value/items/search?account_name=${encodeURIComponent(accountName)}&q=${encodeURIComponent(q)}${loc?'&location='+loc:''}${status?'&status='+status:''}`);
}

export async function runItemsFilter(filter) {
  const accountName = getAccountData()?.account_name;
  if (!accountName) { setItemsStatus('error','Run analysis first.'); return; }
  setItemsStatus('', `<span class="spinner"></span> Loading ${filter} items…`);
  await _doItemsFetch(`/value/items/${filter}?account_name=${encodeURIComponent(accountName)}`);
}

export async function _doItemsFetch(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data) ? data : [];
    const ids = [...new Set(items.map(i=>i.item_id).filter(Boolean))];
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
      tbody.innerHTML = items.map((h,i) => {
        const name = itemName(h.item_id);
        const icon = itemIcon(h.item_id);
        const img = icon ? `<img src="${icon}" width="16" height="16" style="vertical-align:middle;margin-right:4px;border-radius:2px">` : '';
        const locLabels = { material_storage:'Material Storage', bank:'Bank', character:'Character', shared_inventory:'Shared', tradingpost:'TP', wallet:'Wallet' };
        let loc = locLabels[h.location_type] || h.location_type;
        if (h.location_type === 'character' && h.location_ref) loc = 'Char: ' + h.location_ref.split('/')[0];
        let sEl = `<span class="perm-badge granted">Priced</span>`;
        if (h.valuation_status === 'unpriced') sEl = `<span class="perm-badge missing">Unpriced</span>`;
        if (h.valuation_status === 'account_bound') sEl = `<span class="perm-badge missing">Bound</span>`;
        return `<tr style="cursor:pointer" data-item-id="${h.item_id}"><td>${img}<span class="gold-val">${name}</span></td><td>${h.count.toLocaleString()}</td><td class="dim">${loc}</td><td class="gold-val">${h.value_buy?fmtCoinShort(h.value_buy):'—'}</td><td class="gold-val">${h.value_sell?fmtCoinShort(h.value_sell):'—'}</td><td>${sEl}</td></tr>`;
      }).join('');
    }
    tbody.querySelectorAll('tr[data-item-id]').forEach(row => { row.addEventListener('click', () => loadItemDetail(parseInt(row.dataset.itemId))); });
    setItemsStatus('ok', `Found ${items.length} result(s).`);
  } catch(e) { setItemsStatus('error', `Error: ${e.message}`); }
}

export async function loadItemDetail(itemId) {
  const accountName = getAccountData()?.account_name;
  if (!accountName) return;
  document.getElementById('items-detail').classList.remove('hidden');
  document.getElementById('items-results-table').classList.add('hidden');
  document.getElementById('items-detail-title').textContent = `Item #${itemId} Detail`;

  try {
    const [detailRes, listingRes] = await Promise.all([
      fetch(`/value/items/${itemId}/detail?account_name=${encodeURIComponent(accountName)}`),
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

    const tpContainer = document.getElementById('items-detail-tp');
    if (listing && !listing.error) {
      const arb = listing.arbitrage_viable ? `<span class="perm-badge granted">✓ Arbitrage viable (${fmtCoinShort(listing.net_profit)} profit)</span>` : `<span class="perm-badge missing">No arbitrage</span>`;
      tpContainer.innerHTML = `<div class="section-title" style="margin-top:12px">Market Depth</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-bottom:12px">
          <div class="value-stat-box"><div class="vsl-label">Best Buy</div><div class="vsl-value gold-val">${fmtCoinShort(listing.best_buy)}</div><div class="vsl-small dim">qty: ${(listing.best_buy_qty||0).toLocaleString()}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Best Sell</div><div class="vsl-value gold-val">${fmtCoinShort(listing.best_sell)}</div><div class="vsl-small dim">qty: ${(listing.best_sell_qty||0).toLocaleString()}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Spread</div><div class="vsl-value">${fmtCoinShort(listing.spread)}</div><div class="vsl-small dim">ratio: ${((listing.spread_ratio||0)*100).toFixed(1)}%</div></div>
          <div class="value-stat-box"><div class="vsl-label">Buy Depth</div><div class="vsl-value">${(listing.buy_depth_5||0).toLocaleString()}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Sell Depth</div><div class="vsl-value">${(listing.sell_depth_5||0).toLocaleString()}</div></div>
          <div class="value-stat-box"><div class="vsl-label">Profit Margin</div><div class="vsl-value ${listing.net_profit>0?'vs-up':'vs-down'}">${(listing.profit_margin||0).toFixed(1)}%</div></div>
        </div><div style="margin-bottom:12px">${arb}</div>`;
    } else { tpContainer.innerHTML = ''; }

    const locs = document.getElementById('items-detail-locations');
    const entries = Object.entries(detail.locations || {});
    if (!entries.length) { locs.innerHTML = '<div class="dim">No location data.</div>'; }
    else {
      const locLabels = { material_storage:'Material Storage', bank:'Bank', character:'Character', shared_inventory:'Shared Inventory', tradingpost:'Trading Post', wallet:'Wallet' };
      locs.innerHTML = entries.map(([locType, locItems]) => `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px"><div style="font-weight:600;color:var(--gold);margin-bottom:6px">${locLabels[locType]||locType} (${locItems.length} slot(s))</div>${locItems.map(li => {
        let ref = li.location_ref || '';
        if (locType === 'character' && ref) ref = ' (' + ref.split('/')[0] + ')';
        return `<div style="display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px solid var(--border)"><span class="dim">${ref}</span><span>×${li.count.toLocaleString()}</span><span class="gold-val">${fmtCoinShort(li.value_buy)}</span><span>${li.tradable?'<span class="perm-badge granted">Tradable</span>':'<span class="perm-badge missing">Bound</span>'}</span></div>`;
      }).join('')}</div>`).join('');
    }
  } catch(e) { document.getElementById('items-detail-grid').innerHTML = `<div class="dim">Failed: ${e.message}</div>`; }
}

export function setItemsStatus(cls, msg) {
  const el = document.getElementById('items-status');
  el.className = cls === 'error' ? 'error' : '';
  el.innerHTML = msg;
}

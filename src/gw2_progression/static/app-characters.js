// ── Characters ──
const DOLL_ARMOR = [
  { slot:'Helm', col:0, row:0, label:'Helm' }, { slot:'Shoulders', col:1, row:0, label:'Shoulders' },
  { slot:'Coat', col:0, row:1, label:'Coat' }, { slot:'Gloves', col:1, row:1, label:'Gloves' },
  { slot:'Leggings', col:0, row:2, label:'Leggings' }, { slot:'Boots', col:1, row:2, label:'Boots' },
  { slot:'Backpack', col:0, row:3, label:'Back' }, { slot:'Amulet', col:1, row:3, label:'Amulet' },
  { slot:'Accessory1', col:0, row:4, label:'Acc 1' }, { slot:'Accessory2', col:1, row:4, label:'Acc 2' },
  { slot:'Ring1', col:0, row:5, label:'Ring 1' }, { slot:'Ring2', col:1, row:5, label:'Ring 2' },
];
const DOLL_WEAPONS = [
  { slot:'WeaponA1', label:'Main 1' }, { slot:'WeaponA2', label:'Off 1' },
  { slot:'WeaponB1', label:'Main 2' }, { slot:'WeaponB2', label:'Off 2' },
];
let _chars = [];

function renderCharacters(chars) {
  _chars = chars;
  const sel = document.getElementById('char-selector');
  sel.innerHTML = chars.map((c,i) => `<button class="char-btn${i===0?' active':''}" data-idx="${i}">${c.name}</button>`).join('');
  sel.addEventListener('click', e => {
    const btn = e.target.closest('.char-btn');
    if (!btn) return;
    document.querySelectorAll('.char-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active'); showCharacter(parseInt(btn.dataset.idx));
  });
  if (chars.length) showCharacter(0);
}

function showCharacter(idx) {
  const ch = _chars[idx]; if (!ch) return;
  const eqMap = {};
  for (const eq of (ch.equipment||[])) eqMap[eq.slot] = eq;
  const dollSlots = DOLL_ARMOR.map(s => renderDollSlot(s.slot,s.label,eqMap[s.slot])).join('');
  const weaponSlots = DOLL_WEAPONS.map(s => renderDollSlot(s.slot,s.label,eqMap[s.slot])).join('');
  const equipRows = [...DOLL_ARMOR,...DOLL_WEAPONS].map(s => {
    const eq = eqMap[s.slot]; if (!eq) return '';
    const skinId = eq.skin||eq.id; const ic = skinIcon(skinId)||itemIcon(eq.id);
    const name = skinName(skinId)!==`Skin #${skinId}`?skinName(skinId):itemName(eq.id);
    const dyes = (eq.dyes||[]).filter(d=>d!=null).map(d => `<span class="dye-dot" style="background:${colorHex(d)}" title="${(_colorCache[d]||{}).name||''}"></span>`).join('');
    return `<div class="equip-row">${ic?`<img src="${ic}" alt="">`:'<div style="width:32px;height:32px;background:#333;border-radius:2px"></div>'}<span class="eq-slot">${s.label}</span><span class="eq-name">${name}</span><span class="eq-dyes">${dyes}</span></div>`;
  }).filter(Boolean).join('');
  document.getElementById('char-detail').innerHTML = `<div class="char-viewer"><div><div class="paper-doll">${dollSlots}</div><div class="doll-weapons">${weaponSlots}</div></div><div class="char-info"><div class="char-info-header"><div class="char-name">${ch.name}</div><div class="char-meta">${ch.race} · ${ch.profession} · Level ${ch.level} · ${ch.gender}</div>${ch.guild?(()=>{const g=_guildCache[ch.guild]||{}; return `<div style="margin-top:5px"><span style="background:#1e2a1e;border:1px solid #3a5a3a;border-radius:3px;padding:3px 8px;font-size:12px;color:#6bc46b">[${g.tag||'?'}] ${g.name||ch.guild}</span></div>`;})():''}</div><div class="char-stats-grid"><div class="char-stat-box"><div class="cs-label">Playtime</div><div class="cs-val">${Math.round((ch.age||0)/3600)}h</div></div><div class="char-stat-box"><div class="cs-label">Deaths</div><div class="cs-val">${ch.deaths||0}</div></div><div class="char-stat-box"><div class="cs-label">Created</div><div class="cs-val">${(ch.created||'').slice(0,10)}</div></div><div class="char-stat-box"><div class="cs-label">Equipment</div><div class="cs-val">${(ch.equipment||[]).length}</div></div><div class="char-stat-box"><div class="cs-label">Crafting</div><div class="cs-val">${(ch.crafting||[]).map(x=>x.discipline).join(', ')||'—'}</div></div></div><div class="section-title" style="margin-top:0">Equipment</div><div class="equip-list">${equipRows}</div></div></div>`;
}

function renderDollSlot(slot, label, eq) {
  if (!eq) return `<div class="doll-slot"><span class="slot-empty">·</span><span class="slot-label">${label}</span></div>`;
  const skinId = eq.skin||eq.id; const ic = skinIcon(skinId)||itemIcon(eq.id);
  const name = skinName(skinId)!==`Skin #${skinId}`?skinName(skinId):itemName(eq.id);
  const dyes = (eq.dyes||[]).filter(d=>d!=null).map(d=>`<span class="dye-dot" style="background:${colorHex(d)}"></span>`).join('');
  return `<div class="doll-slot"><div class="tooltip">${name}</div>${ic?`<img src="${ic}" alt="${name}">`:'<span class="slot-empty">?</span>'}<span class="slot-label">${label}</span>${dyes?`<div class="dye-row">${dyes}</div>`:''}</div>`;
}

// ── Wardrobe ──
let _allSkinIds = []; let _wardrobeLoaded = false; let _wardrobeFiltered = []; let _wardrobeVisible = 200;
const WARDROBE_PAGE = 200;

function setupWardrobe(skinIds) {
  _allSkinIds = skinIds; _wardrobeLoaded = false; _wardrobeVisible = WARDROBE_PAGE;
  document.querySelectorAll('#nav-tabs button').forEach(btn => {
    if (btn.dataset.tab === 'wardrobe') btn.addEventListener('click', loadWardrobeOnce, { once: false });
  });
  let t = null;
  document.getElementById('wardrobe-search').addEventListener('input', () => { clearTimeout(t); t = setTimeout(resetWardrobePagination, 200); });
  document.getElementById('wardrobe-type').addEventListener('change', () => { populateSubtypes(); resetWardrobePagination(); });
  document.getElementById('wardrobe-subtype').addEventListener('change', resetWardrobePagination);
}
function resetWardrobePagination() { _wardrobeVisible = WARDROBE_PAGE; filterWardrobe(); }
async function loadWardrobeOnce() {
  if (_wardrobeLoaded) return; _wardrobeLoaded = true;
  document.getElementById('wardrobe-loading').classList.remove('hidden');
  await resolveSkins(_allSkinIds);
  document.getElementById('wardrobe-loading').classList.add('hidden');
  populateSubtypes(); filterWardrobe();
}
function populateSubtypes() {
  const tf = document.getElementById('wardrobe-type').value;
  const st = new Set();
  for (const id of _allSkinIds) { const s=_skinCache[id]; if (!s) continue; if (tf&&s.type!==tf) continue; if (s.subtype) st.add(s.subtype); }
  const sel = document.getElementById('wardrobe-subtype');
  const cur = sel.value;
  sel.innerHTML = '<option value="">All subtypes</option>' + [...st].sort().map(st=>`<option value="${st}"${st===cur?' selected':''}>${st}</option>`).join('');
}
function filterWardrobe() {
  const s = document.getElementById('wardrobe-search').value.toLowerCase();
  const tf = document.getElementById('wardrobe-type').value;
  const sf = document.getElementById('wardrobe-subtype').value;
  _wardrobeFiltered = _allSkinIds.filter(id => { const sk=_skinCache[id]; if(!sk) return false; if(tf&&sk.type!==tf) return false; if(sf&&sk.subtype!==sf) return false; if(s&&!sk.name.toLowerCase().includes(s)) return false; return true; });
  renderWardrobePage();
}
function showMoreWardrobe() { _wardrobeVisible += WARDROBE_PAGE; renderWardrobePage(); }
function renderWardrobePage() {
  const total = _wardrobeFiltered.length; const show = Math.min(_wardrobeVisible, total);
  document.getElementById('wardrobe-count').textContent = `Showing ${show.toLocaleString()} of ${total.toLocaleString()} skins`;
  const grid = document.getElementById('skin-grid');
  if (!total) { grid.innerHTML = '<div style="grid-column:1/-1;padding:30px 0;text-align:center;color:var(--text-dim)">No skins match your search criteria.</div>'; return; }
  grid.innerHTML = _wardrobeFiltered.slice(0,show).map(id => {
    const s = _skinCache[id]||{};
    return `<div class="skin-card">${s.icon?`<img src="${s.icon}" alt="${s.name||''}">`:'<div style="width:56px;height:56px;background:#333;border-radius:3px"></div>'}<div class="sk-name">${s.name||`#${id}`}</div><div class="sk-type">${s.subtype||s.type||''}</div></div>`;
  }).join('');
  if (show < total) {
    const lm = document.createElement('div');
    lm.style.cssText = 'grid-column:1/-1;text-align:center;padding:16px 0';
    lm.innerHTML = `<button style="background:var(--gold);border:none;border-radius:3px;color:#111;cursor:pointer;font-size:13px;font-weight:600;padding:8px 20px" onclick="showMoreWardrobe()">Show ${Math.min(WARDROBE_PAGE,total-show).toLocaleString()} more (${(total-show).toLocaleString()} remaining)</button>`;
    grid.appendChild(lm);
  }
}

// ── Wallet ──
function renderWallet(wallet) {
  const sorted = [...wallet].sort((a,b)=>b.value-a.value);
  document.getElementById('wallet-list').innerHTML = sorted.map(w => {
    const name = currencyName(w.id); const desc = (_currencyCache[w.id]||{}).description||'';
    const qty = w.id===1?fmtCoin(w.value):w.value.toLocaleString();
    return `<div class="currency-row"><div class="currency-name">${name}</div><div class="currency-desc">${desc}</div><div class="currency-qty">${qty}</div></div>`;
  }).join('');
}

// ── Inventory ──
function renderInventory(d) {
  const mats = (d.materials||[]).filter(m=>m.count>0).sort((a,b)=>b.count-a.count).slice(0,40);
  document.querySelector('#materials-table tbody').innerHTML = mats.map(m => {
    const ic = itemIcon(m.id); const im = ic?`<img src="${ic}" width="20" height="20" style="vertical-align:middle;margin-right:6px;border-radius:2px">`:'';
    return `<tr><td>${im}<span class="gold-val">${itemName(m.id)}</span></td><td>${m.count.toLocaleString()}</td><td class="dim">${matCatName(m.category)}</td></tr>`;
  }).join('');
  const bank = d.bank||[]; const used = bank.filter(s=>s!==null).length;
  document.getElementById('bank-summary').innerHTML = `<div class="stat-card" style="display:inline-block;min-width:160px"><div class="label">Bank Slots</div><div class="value">${used}/${bank.length}</div><div class="sub">slots occupied</div></div>`;
  const shared = d.shared_inventory;
  const sl = document.getElementById('shared-inv-list');
  if (!shared) { sl.innerHTML = '<div class="dim">No shared inventory data</div>'; return; }
  const slots = Array.isArray(shared)?shared:[shared];
  const items = slots.filter(s=>s!==null);
  if (!items.length) { sl.innerHTML = '<div class="dim">All shared inventory slots are empty</div>'; return; }
  sl.innerHTML = `<div class="stat-card" style="display:inline-block;min-width:160px;margin-bottom:12px"><div class="label">Slots Used</div><div class="value">${items.length}/${slots.length}</div><div class="sub">shared inventory slots</div></div><div style="display:flex;flex-wrap:wrap;gap:8px">${items.map(s => { const ic=itemIcon(s.id); return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:8px;text-align:center;width:80px">${ic?`<img src="${ic}" width="40" height="40" style="border-radius:3px">`:'<div style="width:40px;height:40px;background:#333;border-radius:3px;margin:0 auto"></div>'}<div style="font-size:11px;color:var(--text-dim);margin-top:4px;word-break:break-all">${itemName(s.id)}</div>${s.count>1?`<div style="font-size:11px;color:var(--gold)">×${s.count}</div>`:''}</div>`;}).join('')}</div>`;
}

// ── Progression ──
function renderProgression(d) {
  document.querySelector('#masteries-table tbody').innerHTML = (d.masteries||[]).map(m => `<tr><td class="gold-val">${masteryName(m.id)}</td><td class="dim">${masteryRegion(m.id)}</td><td>${m.level}</td></tr>`).join('')||'<tr><td colspan="3" class="dim">No mastery data</td></tr>';
  const totals = (d.mastery_points?.totals||[]);
  document.getElementById('mastery-point-cards').innerHTML = totals.map(t => `<div class="stat-card"><div class="label">${t.region}</div><div class="value">${t.spent}/${t.earned}</div><div class="sub">spent/earned</div></div>`).join('');
  document.getElementById('achiev-summary').innerHTML = `<div class="stat-card" style="display:inline-block;min-width:200px"><div class="label">Achievements</div><div class="value">${(d.achievements||[]).length.toLocaleString()}</div><div class="sub">tracked on account</div></div>`;
}

// ── PvP ──
function renderPvp(d) {
  const stats = d.pvp_stats||{}; const agg = stats.aggregate||{};
  const wins = agg.wins?.pvp||0; const losses = agg.losses?.pvp||0; const total = wins+losses;
  document.getElementById('pvp-grid').innerHTML = [
    {label:'PvP Rank',value:stats.pvp_rank||'—'},{label:'Wins',value:wins},{label:'Losses',value:losses},
    {label:'Win Rate',value:total?`${Math.round(wins/total*100)}%`:'—'},{label:'Desertions',value:agg.desertions?.pvp||0},{label:'Byes',value:agg.byes?.pvp||0}
  ].map(s => `<div class="pvp-stat"><div class="ps-label">${s.label}</div><div class="ps-val">${s.value}</div></div>`).join('');
  document.querySelector('#pvp-games-table tbody').innerHTML = (d.pvp_games||[]).map(g => `<tr><td>${mapName(g.map_id)}</td><td class="${g.result==='Victory'?'gold-val':'dim'}">${g.result||'—'}</td><td>${g.scores?.red||g.scores?.blue||'—'}</td><td>${g.profession||'—'}</td></tr>`).join('')||'<tr><td colspan="4" class="dim">No recent games</td></tr>';
  const standings = d.pvp_standings||[];
  document.getElementById('pvp-standings-list').innerHTML = standings.length
    ? `<table class="data-table"><thead><tr><th>#</th><th>Team/Division</th><th>Rating</th><th>Wins</th><th>Losses</th></tr></thead><tbody>${standings.map((s,i)=>`<tr><td>${i+1}</td><td>${s.division_name||s.ladder_name||'—'}</td><td class="gold-val">${(s.rating||'—').toLocaleString()}</td><td>${s.wins||'—'}</td><td>${s.losses||'—'}</td></tr>`).join('')}</tbody></table>`
    : '<div class="dim">No ladder standings data</div>';
}

// ── Unlocks ──
function renderUnlocks(d) {
  document.getElementById('unlock-grid').innerHTML = [
    {label:'Skins',val:d.unlocked_skins_count},{label:'Dyes',val:d.unlocked_dyes_count},
    {label:'Minis',val:d.unlocked_minis_count},{label:'Finishers',val:(d.unlocked_finishers||[]).length}
  ].map(u => `<div class="unlock-card"><div class="u-label">${u.label}</div><div class="u-val">${u.val??'—'}</div></div>`).join('');
  document.querySelector('#finishers-table tbody').innerHTML = (d.unlocked_finishers||[]).map(f => `<tr><td class="gold-val">Finisher #${f.id}</td><td>${f.permanent?'Yes':'No'}</td><td>${f.quantity??'∞'}</td></tr>`).join('')||'<tr><td colspan="3" class="dim">None</td></tr>';
}

// ── WvW ──
function renderWvw(d) {
  document.getElementById('wvw-cards').innerHTML = [
    {label:'WvW Rank',value:d.wvw_rank??'—',sub:'account rank'},{label:'WvW Team',value:d.wvw?.wvw_team??'—',sub:'current team'}
  ].map(c => `<div class="stat-card"><div class="label">${c.label}</div><div class="value">${c.value}</div><div class="sub">${c.sub}</div></div>`).join('');
}

// ── Builds ──
function renderBuilds(d) {
  const raw = d.builds||[]; const storage = Array.isArray(raw)?raw[0]:raw;
  const eqTabs = storage?.equipment_tabs||[]; const buildTabs = storage?.build_tabs||[];
  let html = '';
  if (eqTabs.length) {
    html += `<div class="section-title">Equipment Templates (${eqTabs.length})</div>`;
    html += eqTabs.map(t => {
      const items = (t.equipment||[]).map(eq => {
        const ic = itemIcon(eq.id);
        return `<span style="display:inline-block;margin:4px;text-align:center">${ic?`<img src="${ic}" width="32" height="32" style="border-radius:3px;display:block">`:'<div style="width:32px;height:32px;background:#333;border-radius:3px"></div>'}<span style="font-size:10px;color:var(--text-dim)">${(itemName(eq.id)||'#'+eq.id).slice(0,12)}</span></span>`;
      }).join('');
      return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px"><div style="font-weight:600;color:var(--gold);margin-bottom:8px">${t.name||`Tab ${t.tab}`}</div><div>${items||'<span class="dim">Empty</span>'}</div></div>`;
    }).join('');
  }
  if (buildTabs.length) {
    html += `<div class="section-title">Build Templates (${buildTabs.length})</div>`;
    html += buildTabs.map(t => `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:8px"><div style="font-weight:600;color:var(--gold)">${t.name||`Tab ${t.tab}`}</div><div class="dim" style="font-size:12px;margin-top:4px;word-break:break-all">Build ID: ${(t.build||'—').slice(0,80)}</div></div>`).join('');
  }
  if (!html) html = '<div class="dim">No saved builds or equipment templates found.</div>';
  document.getElementById('builds-content').innerHTML = html;
}

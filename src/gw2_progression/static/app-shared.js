// ── SVG Icon Helper ──

const _spriteLoaded = false;

export function loadIconSprite() {
  if (_spriteLoaded) return;
  fetch('/static/icons.svg?v=20260627')
    .then(r => r.text())
    .then(html => {
      document.body.insertAdjacentHTML('afterbegin', html);
    })
    .catch(() => {});
}

export function icon(name, size = 20) {
  return `<svg class="gw2-icon" width="${size}" height="${size}" aria-hidden="true"><use href="#${name}"/></svg>`;
}

// ── Shared Cache & Utils ──
export const MAX_CACHE_SIZE = 5000;

export const _itemCache    = {};
export const _currencyCache= {};
export const _matCatCache  = {};
export const _masteryCache = {};
export const _mapCache     = {};
export const _skinCache    = {};
export const _colorCache   = {};
export const _guildCache   = {};

let _accountData = null;
let _valueCharts = {};
export function getAccountData() { return _accountData; }
export function setAccountData(v) { _accountData = v; }
export function getValueCharts() { return _valueCharts; }
export function setValueCharts(v) { _valueCharts = v; }

export async function backendResolve(type, ids) {
  const res = await fetch('/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, ids: ids.map(String) }),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function backendResolveSingle(type, id) {
  const res = await fetch('/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, id: String(id) }),
  });
  if (!res.ok) return null;
  return res.json();
}

export function cappedCacheAdd(cache, key, val) {
  if (Object.keys(cache).length >= MAX_CACHE_SIZE) {
    const oldest = Object.keys(cache)[0];
    delete cache[oldest];
  }
  cache[key] = val;
}

export async function resolveItems(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _itemCache));
  if (!missing.length) return;
  const data = await backendResolve('items', missing);
  for (const item of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_itemCache, item.id, { name: item.name, icon: item.icon });
  }
}

export async function resolveCurrencies(ids) {
  const missing = [...new Set(ids)].filter(id => !(id in _currencyCache));
  if (!missing.length) return;
  const data = await backendResolve('currencies', missing);
  for (const c of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_currencyCache, c.id, { name: c.name, description: c.description });
  }
}

export async function resolveMatCategories() {
  if (Object.keys(_matCatCache).length) return;
  const data = await backendResolve('materials', []);
  for (const cat of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_matCatCache, cat.id, cat.name);
  }
}

export async function resolveMasteries(ids) {
  const missing = [...new Set(ids)].filter(id => !(id in _masteryCache));
  if (!missing.length) return;
  const data = await backendResolve('masteries', missing);
  for (const m of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_masteryCache, m.id, { name: m.name, region: m.region });
  }
}

export async function resolveMaps(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _mapCache));
  if (!missing.length) return;
  const data = await backendResolve('maps', missing);
  for (const m of (Array.isArray(data) ? data : [])) {
    cappedCacheAdd(_mapCache, m.id, m.name);
  }
}

export async function resolveSkins(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _skinCache));
  if (!missing.length) return;
  const data = await backendResolve('skins', missing);
  for (const s of (Array.isArray(data) ? data : [])) {
    const subtype = s.details?.type || s.details?.weight_class || '';
    cappedCacheAdd(_skinCache, s.id, { name: s.name, icon: s.icon, type: s.type, subtype });
  }
}

export async function resolveGuilds(ids) {
  const missing = [...new Set(ids)].filter(id => id && !(id in _guildCache));
  await Promise.all(missing.map(async id => {
    const data = await backendResolveSingle('guild', id);
    cappedCacheAdd(_guildCache, id, data ? { name: data.name, tag: data.tag } : { name: 'Unknown Guild', tag: '?' });
  }));
}

export async function resolveColors(ids) {
  const missing = [...new Set(ids)].filter(id => id != null && !(id in _colorCache));
  if (!missing.length) return;
  const data = await backendResolve('colors', missing);
  for (const c of (Array.isArray(data) ? data : [])) {
    const rgb = c.cloth?.rgb || c.leather?.rgb || c.metal?.rgb || [128, 128, 128];
    cappedCacheAdd(_colorCache, c.id, { name: c.name, hex: rgbToHex(rgb) });
  }
}

export async function resolveSearch(query) {
  const res = await fetch('/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'search_items', query: String(query) }),
  });
  if (!res.ok) return [];
  return res.json();
}

export function rgbToHex([r, g, b]) {
  return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
}

export function itemName(id)    { return _itemCache[id]?.name    || `Item #${id}`; }
export function itemIcon(id)    { return _itemCache[id]?.icon    || null; }
export function currencyName(id){ return _currencyCache[id]?.name || `Currency #${id}`; }
export function matCatName(id)  { return _matCatCache[id]        || `Category #${id}`; }
export function masteryName(id) { return _masteryCache[id]?.name || `Mastery #${id}`; }
export function masteryRegion(id){ return _masteryCache[id]?.region || '—'; }
export function mapName(id)     { return _mapCache[id]           || `Map #${id}`; }
export function skinName(id)    { return _skinCache[id]?.name    || `Skin #${id}`; }
export function skinIcon(id)    { return _skinCache[id]?.icon    || null; }
export function colorHex(id)    { return id != null ? (_colorCache[id]?.hex || '#888') : null; }

export function fmtCoin(copper) {
  if (!copper) return '0g 0s 0c';
  const sign = copper < 0 ? '-' : '';
  const abs = Math.abs(copper);
  return `${sign}${Math.floor(abs/10000)}g ${Math.floor((abs%10000)/100)}s ${abs%100}c`;
}

export function fmtCoinShort(copper) {
  if (!copper) return '0g';
  const abs = Math.abs(copper);
  const g = Math.floor(abs / 10000);
  const s = Math.floor((abs % 10000) / 100);
  if (g > 0) return `${g}g`;
  if (s > 0) return `${s}s`;
  return `${abs}c`;
}

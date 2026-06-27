// ── Insight Page — AI Overlay Layer ──

import { fmtCoin, fmtCoinShort } from './app-shared.js';

let _sessionToken = null;

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    if (page === 'account') window.location.href = '/account';
    else if (page === 'plan') window.location.href = '/plan';
  });

  try {
    const saved = localStorage.getItem('gw2_session');
    if (saved) {
      _sessionToken = saved;
      loadInsight(saved);
      const keyInput = document.getElementById('insight-api-key');
      if (keyInput) { keyInput.value = saved; }
    }
  } catch(e) {}
});

async function loadInsight(token) {
  const container = document.getElementById('insight-recommendations');
  container.innerHTML = '<div class="dim" style="text-align:center;padding:30px"><span class="spinner"></span> Loading insights…</div>';

  try {
    // Fetch AI insight data
    const insightRes = await fetch(`/api/insight/data?api_key=${encodeURIComponent(token)}`);
    if (!insightRes.ok) throw new Error('Failed to load insights');
    const data = await insightRes.json();

    document.getElementById('insight-account-badge').classList.remove('hidden');
    document.getElementById('insight-account-name').textContent = data.account_name || '—';

    // Hidden Wealth
    const hiddenWealthCount = data.hidden_wealth?.item_count || 0;
    const hiddenWealthHtml = hiddenWealthCount > 0
      ? `${hiddenWealthCount} unpriced items`
      : 'All items priced';
    document.getElementById('insight-hidden-wealth').textContent = hiddenWealthHtml;
    document.getElementById('insight-hidden-wealth-detail').textContent = data.hidden_wealth?.explanation || '';

    // Build Readiness
    const br = data.build_readiness || {};
    const buildReadyHtml = `${br.equipped_chars || 0} / ${br.total_chars || 0} chars equipped`;
    document.getElementById('insight-build-ready').textContent = buildReadyHtml;
    const brDetail = br.missing_gear_chars > 0
      ? `${br.missing_gear_chars} characters at 80 with missing gear data`
      : 'All level 80 characters have equipment';
    document.getElementById('insight-build-ready-detail').textContent = brDetail;

    // Legendary Progress (placeholder — needs goal service integration)
    document.getElementById('insight-legendary').textContent = '—';
    document.getElementById('insight-legendary-detail').textContent = 'Track goals on the Plan page';

    // Top Items (recommendations)
    const topItems = data.top_items || [];
    const topMaterials = data.top_materials || [];

    let recHtml = '';

    if (topItems.length > 0) {
      recHtml += '<div style="font-size:11px;color:var(--gw2-text-dim);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">Highest Value Items</div>';
      for (const item of topItems.slice(0, 3)) {
        const val = item.value_sell || 0;
        recHtml += `
          <div class="rec-item">
            <span class="rec-text"><strong>Item #${item.item_id}</strong> × ${item.count} in ${item.location}</span>
            <span class="rec-reward">${fmtCoin(val)}</span>
          </div>`;
      }
    }

    if (topMaterials.length > 0) {
      recHtml += '<div style="font-size:11px;color:var(--gw2-text-dim);text-transform:uppercase;letter-spacing:1.5px;margin:12px 0 8px">Top Materials by Value</div>';
      for (const mat of topMaterials.slice(0, 3)) {
        recHtml += `
          <div class="rec-item">
            <span class="rec-text"><strong>Item #${mat.item_id}</strong> × ${mat.count}</span>
            <span class="rec-reward">${fmtCoin(mat.value_sell)}</span>
          </div>`;
      }
    }

    if (!recHtml) {
      recHtml = '<div class="dim" style="text-align:center;padding:20px">Analyze your account first.</div>';
    }

    container.innerHTML = recHtml;

  } catch(e) {
    container.innerHTML = '<div class="dim" style="text-align:center;padding:20px">Unable to load insights. Check your API key.</div>';
    console.warn('Insight error:', e);
  }
}

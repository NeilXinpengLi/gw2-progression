// ── Insight Page — AI Overlay Layer ──

import { fmtCoin, fmtCoinShort } from './app-shared.js';
import { initSession } from './session-manager.js';

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  const token = await initSession();
  if (token) {
    loadInsight(token);
  } else {
    document.getElementById('insight-recommendations').innerHTML =
      '<div class="dim" style="text-align:center;padding:30px">Connect your account on the Account page first.</div>';
  }
});

async function loadInsight(token) {
  const container = document.getElementById('insight-recommendations');
  container.innerHTML = '<div class="dim" style="text-align:center;padding:30px"><span class="spinner"></span> Loading insights…</div>';

  try {
    const res = await fetch(`/api/insight/data?api_key=${encodeURIComponent(token)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    document.getElementById('insight-account-badge')?.classList.remove('hidden');
    document.getElementById('insight-account-name').textContent = data.account_name || '—';

    // Hidden Wealth
    const hiddenCount = data.hidden_wealth?.item_count || 0;
    document.getElementById('insight-hidden-wealth').textContent = hiddenCount > 0 ? `${hiddenCount} items` : 'All items priced';
    document.getElementById('insight-hidden-wealth-detail').textContent = data.hidden_wealth?.explanation || '';

    // Build Readiness
    const br = data.build_readiness || {};
    document.getElementById('insight-build-ready').textContent = `${br.equipped_chars || 0}/${br.total_chars || 0} chars equipped`;
    document.getElementById('insight-build-ready-detail').textContent =
      br.missing_gear_chars > 0
        ? `${br.missing_gear_chars} chars at 80 missing gear data`
        : 'All level 80 characters have equipment';

    // Legendary Progress
    const leg = data.legendary_progress || {};
    const activeGoals = leg.active_goals || [];
    document.getElementById('insight-legendary').textContent =
      activeGoals.length > 0
        ? `${activeGoals.length} active (${Math.round(activeGoals.reduce((a, g) => a + (g.completion_percent || 0), 0) / activeGoals.length)}% avg)`
        : leg.total > 0 ? `${leg.total} goals (all completed)` : 'No goals tracked';
    document.getElementById('insight-legendary-detail').textContent =
      activeGoals.length > 0
        ? activeGoals.slice(0, 3).map(g => `#${g.target_item_id}: ${Math.round(g.completion_percent || 0)}%`).join(' · ')
        : 'Track goals on the Plan page';

    // Top Items + Market Insight
    const topItems = data.top_items || [];
    const market = data.market_insight || {};
    const sellCandidates = market.sell_candidates || [];

    let recHtml = '';

    if (topItems.length > 0) {
      recHtml += '<div style="font-size:10px;color:var(--gw2-text-dim);text-transform:uppercase;letter-spacing:2px;margin-bottom:8px">Highest Value Items</div>';
      for (const item of topItems.slice(0, 3)) {
        recHtml += `
          <div class="rec-item">
            <span class="rec-text"><strong>Item #${item.item_id}</strong> ×${item.count} in ${item.location}</span>
            <span class="rec-reward">${fmtCoin(item.value_sell)}</span>
          </div>`;
      }
    }

    if (sellCandidates.length > 0) {
      recHtml += '<div style="font-size:10px;color:var(--gw2-text-dim);text-transform:uppercase;letter-spacing:2px;margin:14px 0 8px">High-Liquidity Sell Candidates</div>';
      for (const sc of sellCandidates.slice(0, 3)) {
        recHtml += `
          <div class="rec-item">
            <span class="rec-text"><strong>Item #${sc.item_id}</strong> spread: ${(sc.spread_ratio * 100).toFixed(1)}%</span>
          </div>`;
      }
    }

    if (!recHtml) {
      recHtml = '<div class="dim" style="text-align:center;padding:20px">No insights available. Run an analysis first.</div>';
    }
    container.innerHTML = recHtml;

  } catch (e) {
    container.innerHTML = '<div class="dim" style="text-align:center;padding:20px">Unable to load insights. Check your connection.</div>';
    console.warn('Insight error:', e);
  }
}

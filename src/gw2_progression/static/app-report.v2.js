// Report Page - Monetization Layer
import { initSession } from './session-manager.js';
import { fmtCoin } from './app-shared.js';

let _accountName = '';
let _productsBySlug = {};

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('os-nav')?.addEventListener('click', e => {
    const btn = e.target.closest('button[data-nav]');
    if (!btn) return;
    const page = btn.dataset.nav;
    const urls = { account: '/account', insight: '/insight', plan: '/plan', report: '/report' };
    if (urls[page]) window.location.href = urls[page];
  });

  const token = await initSession();
  if (token) loadReport(token);
  loadProducts();

  document.querySelectorAll('.checkout-btn').forEach(btn => {
    btn.addEventListener('click', () => startCheckout(btn));
  });
});

async function loadReport(token) {
  try {
    const r = await fetch(`/api/account/overview?api_key=${encodeURIComponent(token)}`);
    if (!r.ok) return;
    const d = await r.json();

    _accountName = d.account?.name || '';
    document.getElementById('report-account-name').textContent = _accountName || '-';
    document.getElementById('report-total-value').textContent = fmtCoin(d.kpis?.account_value || 0);
    document.getElementById('report-char-count').textContent = `${d.kpis?.character_count || 0} characters`;
    document.getElementById('report-build-ready').textContent = `${d.kpis?.build_ready_count ?? '-'} ready`;
  } catch(e) {
    console.warn('Report load error:', e);
  }
}

async function loadProducts() {
  try {
    const res = await fetch('/commercial/products');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _productsBySlug = Object.fromEntries((data.products || []).map(product => [product.slug, product]));
  } catch(e) {
    console.warn('Product load error:', e);
  }
}

async function startCheckout(button) {
  const slug = button.dataset.productSlug;
  const product = _productsBySlug[slug];
  if (!product) {
    showCheckoutStatus('Product catalog is still loading. Try again in a moment.', true);
    await loadProducts();
    return;
  }

  const customerEmail = window.prompt('Email for your license key:');
  if (!customerEmail) return;

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = 'Processing...';
  showCheckoutStatus('', false);

  try {
    const res = await fetch('/commercial/checkout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        product_id: product.id,
        customer_email: customerEmail.trim(),
        account_name: _accountName,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    const license = data.order?.license_key;
    showCheckoutStatus(license ? `License created: ${license}` : (data.message || 'Order created.'), false);
  } catch(e) {
    showCheckoutStatus(e.message || String(e), true);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function showCheckoutStatus(message, isError) {
  let status = document.getElementById('checkout-status');
  if (!status) {
    status = document.createElement('div');
    status.id = 'checkout-status';
    status.style.marginTop = '12px';
    status.style.fontSize = '12px';
    document.querySelector('.pricing-grid')?.after(status);
  }
  status.textContent = message;
  status.style.color = isError ? '#ff9b9b' : 'var(--gw2-text)';
}

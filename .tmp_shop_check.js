(function () {
  const { qs, qsa, apiRequest, requireAuth, toast, formatError, moneyFromCents, escapeHtml: esc, loadShopCache, saveShopCache } = window.App;

  const state = {
    products: [],
    currentProvider: 'codex',
    selectedProduct: null,
    inventory: {},
    purchaseQty: 1,
    selectedPayType: 'alipay',
    activePollingOrderNo: null,
    paymentPollingTimer: null,
    paymentPollingAttempts: 0,
    lastPurchase: { sku: null, codesText: '' },
    isCreatingOrder: false
  };

  const MAX_PURCHASE_QTY = 50;
  const PAYMENT_POLL_INTERVAL_MS = 2500;
  const PAYMENT_POLL_MAX_ATTEMPTS = 240;

  function normalizeQty(value, maxQty) {
    const n = parseInt(value, 10);
    if (!Number.isFinite(n)) return 1;
    return Math.min(Math.max(1, n), maxQty);
  }

  function resolvePriceCents(product) {
    const discount = product?.discount_percent;
    if (discount !== null && discount !== undefined && discount > 0 && discount < 100) {
      return Math.max(1, Math.round(product.price_cents * discount / 100));
    }
    return product.price_cents;
  }

  function buildShopCachePayload() {
    return {
      codex: state.products?.codex || [],
      gemini: state.products?.gemini || [],
      claude: state.products?.claude || [],
      inventory: state.inventory || {},
    };
  }

  function applyCachedShopData(data) {
    if (!data) return false;
    state.products = {
      codex: data.codex || [],
      gemini: data.gemini || [],
      claude: data.claude || [],
    };
    state.inventory = data.inventory || {};
    renderProducts();
    return true;
  }

  function formatDiscountLabel(percent) {
    if (!percent || percent <= 0 || percent >= 100) return '';
    const fold = percent / 10;
    const label = Number.isInteger(fold) ? fold.toFixed(0) : fold.toFixed(1);
    return `${label}折`;
  }

  // 初始化主题
  function initTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  }

  // 鍒囨崲涓婚
  function toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const newTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  }

  // 加载产品和库存
  async function loadProducts() {
    try {
      try {
        const categorized = await apiRequest('/products/by-category-with-inventory');
        state.products = {
          codex: categorized?.codex || [],
          gemini: categorized?.gemini || [],
          claude: categorized?.claude || [],
        };
        state.inventory = categorized?.inventory || {};
        renderProducts();
        if (saveShopCache) saveShopCache(buildShopCachePayload());
        return;
      } catch (e) {
        console.warn('Fallback to legacy product inventory flow', e);
      }

      const categorized = await apiRequest('/products/by-category');
      state.products = categorized;

      renderProducts();

      // 鑾峰彇搴撳瓨淇℃伅锛堝苟琛岋級
      loadInventory()
        .then(() => {
          renderProducts();
          if (saveShopCache) saveShopCache(buildShopCachePayload());
        })
        .catch((e) => console.error('Failed to load inventory', e));
    } catch (e) {
      toast({ title: '鍔犺浇澶辫触', message: formatError(e), type: 'error' });
    }
  }

  // 鍔犺浇搴撳瓨淇℃伅
  async function loadInventory() {
    const providers = ['codex', 'gemini', 'claude'];
    const skus = [];
    const seen = new Set();
    for (const provider of providers) {
      const products = state.products[provider] || [];
      for (const p of products) {
        const sku = String(p.sku || '').trim();
        if (!sku || seen.has(sku)) continue;
        seen.add(sku);
        skus.push(sku);
      }
    }
    if (skus.length === 0) return;

    try {
      const data = await apiRequest('/products/inventory/batch', { method: 'POST', body: { skus } });
      const items = Array.isArray(data?.items) ? data.items : [];
      const received = new Set();
      items.forEach((item) => {
        if (!item || !item.sku) return;
        state.inventory[item.sku] = item.available || 0;
        received.add(item.sku);
      });
      skus.forEach((sku) => {
        if (!received.has(sku)) state.inventory[sku] = 0;
      });
    } catch (e) {
      skus.forEach((sku) => {
        state.inventory[sku] = 0;
      });
      throw e;
    }
  }

  // 娓叉煋浜у搧鍒楄〃
  function renderProducts() {
    const grid = qs('#productGrid');
    const products = state.products[state.currentProvider] || [];

    if (products.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="icon">馃摝</div>
          <div class="text">该分类暂无产品</div>
        </div>
      `;
      return;
    }

    grid.innerHTML = products.map(p => {
      const stock = state.inventory[p.sku];
      const hasStock = typeof stock === 'number';
      const stockValue = hasStock ? stock : 0;
      const isLow = hasStock && stockValue > 0 && stockValue < 10;
      const stockClass = !hasStock ? 'stock-loading' : (isLow ? 'stock-low' : '');
      const stockText = !hasStock ? '库存: 加载中...' : (stockValue > 0 ? `库存: ${stockValue}` : '暂时缺货');

      const spec = p.kind === 'day'
        ? `${p.duration_days} 天卡`
        : `$${p.usage_usd} 按量卡`;
      const unitPriceCents = resolvePriceCents(p);
      const hasDiscount = unitPriceCents !== p.price_cents;
      const priceSuffix = p.kind === 'day' ? '张' : '个';
      const discountLabel = formatDiscountLabel(p.discount_percent);
      const priceHtml = hasDiscount
        ? `<span class="price-discount">${moneyFromCents(unitPriceCents, p.currency)}</span><span class="price-original">${moneyFromCents(p.price_cents, p.currency)}</span><small>/${priceSuffix}</small>`
        : `<span class="price-regular">${moneyFromCents(p.price_cents, p.currency)}</span><small>/${priceSuffix}</small>`;
      const discountBadge = discountLabel ? `<span class="discount-badge">${discountLabel}</span>` : '';

      return `
        <div class="product-card ${state.currentProvider}" data-sku="${p.sku}" data-price="${unitPriceCents}">
          <span class="badge badge-sku">${esc(p.sku)}</span>
          <div class="provider-name">${esc(p.provider).toUpperCase()}</div>
          <div class="product-name">${esc(p.name)}</div>
          <div class="product-spec-row">
            <span class="product-spec">${spec}</span>
            ${discountBadge}
          </div>
          <div class="product-price">
            <span class="price-main">${priceHtml}</span>
          </div>
          <div class="stock-info ${stockClass}">
            ${stockText}
          </div>
        </div>
      `;
    }).join('');

    // 缁戝畾鐐瑰嚮浜嬩欢
    qsa('.product-card').forEach(card => {
      card.addEventListener('click', () => {
        const sku = card.dataset.sku;
        const product = products.find(p => p.sku === sku);
        if (product) {
          showConfirmModal(product);
        }
      });
    });
  }

  // 鏄剧ず纭寮圭獥
  function showConfirmModal(product) {
    state.selectedProduct = product;
    const stock = state.inventory[product.sku] || 0;
    const maxQty = Math.max(1, Math.min(stock, MAX_PURCHASE_QTY));
    state.purchaseQty = 1;

    if (stock <= 0) {
      toast({ title: '库存不足', message: '该产品暂时缺货，请稍后再试', type: 'error' });
      return;
    }

    const spec = product.kind === 'day'
      ? `${product.duration_days} 天卡`
      : `$${product.usage_usd} 按量卡`;
    const unitPriceCents = resolvePriceCents(product);
    const hasDiscount = unitPriceCents !== product.price_cents;
    const priceHtml = hasDiscount
      ? `<span class="price-discount">${moneyFromCents(unitPriceCents, product.currency)}</span><span class="price-original">${moneyFromCents(product.price_cents, product.currency)}</span>`
      : `<span class="price-regular">${moneyFromCents(product.price_cents, product.currency)}</span>`;

    state.selectedPayType = 'alipay';

    qs('#confirmContent').innerHTML = `
      <div style="margin-bottom: 12px;">
        <strong>产品：</strong>${esc(product.name)}<br>
        <strong>规格：</strong>${spec}<br>
        <strong>单价：</strong>${priceHtml}<br>
        <strong>库存：</strong>${stock}
      </div>

      <div class="field" style="margin-top: 10px;">
        <label>璐拱鏁伴噺</label>
        <div class="row" style="gap: 10px; align-items: center;">
          <button class="btn small" id="qtyMinusBtn" type="button" style="width: 42px;">-</button>
          <input class="input" id="purchaseQty" type="number" min="1" max="${maxQty}" value="1" style="width: 120px;" />
          <button class="btn small" id="qtyPlusBtn" type="button" style="width: 42px;">+</button>
          <span class="muted-2">最多 ${maxQty} 张</span>
        </div>
      </div>

      <div class="field" style="margin-top: 12px;">
        <label>鏀粯鏂瑰紡</label>
        <div class="row" style="gap: 12px; flex-wrap: wrap; margin-top: 6px;">
          <label class="muted-2" style="display: inline-flex; gap: 6px; align-items: center;">
            <input type="radio" name="purchasePayType" value="alipay" checked />
            支付宝
          </label>
          <label class="muted-2" style="display: inline-flex; gap: 6px; align-items: center;">
            <input type="radio" name="purchasePayType" value="wxpay" />
            寰俊鏀粯
          </label>
        </div>
      </div>

      <div class="card inner" style="margin-top: 12px;">
        <div class="bd">
          <div class="row" style="justify-content: space-between; margin-bottom: 8px;">
            <span class="muted">鎬讳环</span>
            <span id="confirmTotalPrice">${moneyFromCents(unitPriceCents, product.currency)}</span>
          </div>
          <div class="row" style="justify-content: space-between;">
            <span class="muted" id="confirmAfterLabel">鏀粯閫氶亾</span>
            <span id="confirmAfterBalance">支付宝</span>
          </div>
        </div>
      </div>

      <div id="confirmStatusText" style="margin-top: 10px; font-weight: 600;"></div>
    `;

    qs('#confirmModal').classList.remove('hidden');

    const confirmBtn = qs('#confirmPurchaseBtn');
    const qtyInput = qs('#purchaseQty');
    const minusBtn = qs('#qtyMinusBtn');
    const plusBtn = qs('#qtyPlusBtn');
    const totalEl = qs('#confirmTotalPrice');
    const afterLabelEl = qs('#confirmAfterLabel');
    const afterEl = qs('#confirmAfterBalance');
    const statusEl = qs('#confirmStatusText');
    const payTypeInputs = qsa('input[name="purchasePayType"]', qs('#confirmContent'));

    function getSelectedPayType() {
      const selected = payTypeInputs.find((input) => input.checked);
      return selected ? selected.value : 'alipay';
    }

    function updateConfirmSummary() {
      const qty = normalizeQty(qtyInput.value, maxQty);
      state.purchaseQty = qty;
      qtyInput.value = String(qty);
      state.selectedPayType = getSelectedPayType();

      const totalCost = unitPriceCents * qty;

      totalEl.textContent = moneyFromCents(totalCost, product.currency);
      confirmBtn.textContent = '去支付';
      afterLabelEl.textContent = '支付渠道';
      afterEl.textContent = state.selectedPayType === 'alipay' ? '支付宝' : '微信支付';
      afterEl.style.color = 'var(--text)';
      statusEl.textContent = '将打开支付页面，完成支付后系统会自动发货。';
      statusEl.style.color = 'var(--text)';
      confirmBtn.disabled = false;
      confirmBtn.classList.remove('disabled');
    }

    qtyInput.addEventListener('input', updateConfirmSummary);
    minusBtn.addEventListener('click', () => {
      qtyInput.value = String(normalizeQty((parseInt(qtyInput.value, 10) || 1) - 1, maxQty));
      updateConfirmSummary();
    });
    plusBtn.addEventListener('click', () => {
      qtyInput.value = String(normalizeQty((parseInt(qtyInput.value, 10) || 1) + 1, maxQty));
      updateConfirmSummary();
    });
    payTypeInputs.forEach((input) => input.addEventListener('change', updateConfirmSummary));

    updateConfirmSummary();
  }

  // 闅愯棌纭寮圭獥
  function hideConfirmModal() {
    qs('#confirmModal').classList.add('hidden');
    state.selectedProduct = null;
  }

  function showPurchaseSuccess(sku, codes) {
    const codeList = Array.isArray(codes) ? codes : [];
    state.lastPurchase = { sku, codesText: codeList.join('\n') };
    qs('#cardCodeDisplay').textContent = state.lastPurchase.codesText;
    if (qs('#purchaseMeta')) qs('#purchaseMeta').textContent = `SKU: ${sku} | 鏁伴噺: ${codeList.length}`;
    qs('#successModal').classList.remove('hidden');
  }

  function detectEpayDevice() {
    const ua = (navigator.userAgent || '').toLowerCase();
    if (ua.includes('micromessenger')) return 'wechat';
    if (ua.includes('alipayclient')) return 'alipay';
    if (ua.includes('qq/')) return 'qq';
    if (/iphone|ipad|ipod|android|mobile/.test(ua)) return 'mobile';
    return 'pc';
  }

  function readOrderNoFromQuery() {
    try {
      return (new URLSearchParams(window.location.search).get('epay_order_no') || '').trim();
    } catch (e) {
      return '';
    }
  }

  function clearOrderNoFromQuery() {
    try {
      const url = new URL(window.location.href);
      if (!url.searchParams.has('epay_order_no')) return;
      url.searchParams.delete('epay_order_no');
      const query = url.searchParams.toString();
      const next = `${url.pathname}${query ? `?${query}` : ''}${url.hash || ''}`;
      window.history.replaceState({}, '', next);
    } catch (e) {
      console.warn('Failed to clear epay_order_no query', e);
    }
  }

  function stopPaymentPolling() {
    if (state.paymentPollingTimer) {
      window.clearInterval(state.paymentPollingTimer);
      state.paymentPollingTimer = null;
    }
    state.activePollingOrderNo = null;
    state.paymentPollingAttempts = 0;
  }

  function startPaymentPolling(orderNo) {
    const normalizedOrderNo = String(orderNo || '').trim();
    if (!normalizedOrderNo) return;
    if (state.activePollingOrderNo === normalizedOrderNo && state.paymentPollingTimer) return;

    stopPaymentPolling();
    state.activePollingOrderNo = normalizedOrderNo;
    state.paymentPollingAttempts = 0;
    let requesting = false;


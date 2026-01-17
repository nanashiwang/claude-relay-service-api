(function () {
  const { qs, qsa, apiRequest, requireAuth, toast, formatError, moneyFromCents, escapeHtml: esc } = window.App;

  const state = {
    products: [],
    wallet: null,
    currentProvider: 'codex',
    selectedProduct: null,
    inventory: {},
    purchaseQty: 1,
    lastPurchase: { sku: null, codesText: '' }
  };

  const MAX_PURCHASE_QTY = 50;

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

  // 切换主题
  function toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const newTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  }

  // 加载钱包信息
  async function loadWallet() {
    try {
      state.wallet = await apiRequest('/wallet');
      qs('#balanceText').textContent = moneyFromCents(state.wallet.balance_cents, state.wallet.currency);
    } catch (e) {
      qs('#balanceText').textContent = '加载失败';
    }
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
        return;
      } catch (e) {
        console.warn('Fallback to legacy product inventory flow', e);
      }

      const categorized = await apiRequest('/products/by-category');
      state.products = categorized;

      renderProducts();

      // 获取库存信息（并行）
      loadInventory()
        .then(() => renderProducts())
        .catch((e) => console.error('Failed to load inventory', e));
    } catch (e) {
      toast({ title: '加载失败', message: formatError(e), type: 'error' });
    }
  }

  // 加载库存信息
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

  // 渲染产品列表
  function renderProducts() {
    const grid = qs('#productGrid');
    const products = state.products[state.currentProvider] || [];

    if (products.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="icon">📦</div>
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
      const stockText = !hasStock ? '库存: 加载中' : (stockValue > 0 ? `库存: ${stockValue}` : '暂时缺货');

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

    // 绑定点击事件
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

  // 显示确认弹窗
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

    const currentCents = state.wallet?.balance_cents || 0;
    const currentCurrency = state.wallet?.currency || 'CNY';

    qs('#confirmContent').innerHTML = `
      <div style="margin-bottom: 12px;">
        <strong>产品：</strong>${esc(product.name)}<br>
        <strong>规格：</strong>${spec}<br>
        <strong>单价：</strong>${priceHtml}<br>
        <strong>库存：</strong>${stock}<br>
        <strong>当前余额：</strong>${moneyFromCents(currentCents, currentCurrency)}
      </div>

      <div class="field" style="margin-top: 10px;">
        <label>购买数量</label>
        <div class="row" style="gap: 10px; align-items: center;">
          <button class="btn small" id="qtyMinusBtn" type="button" style="width: 42px;">-</button>
          <input class="input" id="purchaseQty" type="number" min="1" max="${maxQty}" value="1" style="width: 120px;" />
          <button class="btn small" id="qtyPlusBtn" type="button" style="width: 42px;">+</button>
          <span class="muted-2">最多 ${maxQty} 张</span>
        </div>
      </div>

      <div class="card inner" style="margin-top: 12px;">
        <div class="bd">
          <div class="row" style="justify-content: space-between; margin-bottom: 8px;">
            <span class="muted">总价</span>
            <span id="confirmTotalPrice">${moneyFromCents(unitPriceCents, product.currency)}</span>
          </div>
          <div class="row" style="justify-content: space-between;">
            <span class="muted">购买后余额</span>
            <span id="confirmAfterBalance">${moneyFromCents(Math.max(0, currentCents - unitPriceCents), currentCurrency)}</span>
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
    const afterEl = qs('#confirmAfterBalance');
    const statusEl = qs('#confirmStatusText');

    function updateConfirmSummary() {
      const qty = normalizeQty(qtyInput.value, maxQty);
      state.purchaseQty = qty;
      qtyInput.value = String(qty);

      const totalCost = unitPriceCents * qty;
      const afterCents = currentCents - totalCost;

      totalEl.textContent = moneyFromCents(totalCost, product.currency);
      afterEl.textContent = moneyFromCents(Math.max(0, afterCents), currentCurrency);

      if (totalCost > currentCents) {
        statusEl.textContent = '⚠️ 余额不足，请先充值';
        statusEl.style.color = 'var(--danger)';
        confirmBtn.disabled = true;
        confirmBtn.classList.add('disabled');
        afterEl.style.color = 'var(--danger)';
      } else {
        statusEl.textContent = '✓ 余额充足，可以购买';
        statusEl.style.color = 'var(--success)';
        confirmBtn.disabled = false;
        confirmBtn.classList.remove('disabled');
        afterEl.style.color = 'var(--text)';
      }
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

    updateConfirmSummary();
  }

  // 隐藏确认弹窗
  function hideConfirmModal() {
    qs('#confirmModal').classList.add('hidden');
    state.selectedProduct = null;
  }

  // 执行购买
  async function purchaseCard() {
    const product = state.selectedProduct;
    if (!product) return;

    const quantity = Math.min(Math.max(1, state.purchaseQty || 1), MAX_PURCHASE_QTY);

    const btn = qs('#confirmPurchaseBtn');
    btn.disabled = true;
    btn.textContent = '购买中...';

    try {
      const result = await apiRequest('/cards/claim-batch-by-login', {
        method: 'POST',
        body: { sku: product.sku, quantity }
      });

      hideConfirmModal();
      loadWallet();
      loadInventory();
      renderProducts();

      // 显示成功弹窗
      const codes = Array.isArray(result.card_codes) ? result.card_codes : (result.card_code ? [result.card_code] : []);
      state.lastPurchase = { sku: product.sku, codesText: codes.join('\n') };
      qs('#cardCodeDisplay').textContent = state.lastPurchase.codesText;
      if (qs('#purchaseMeta')) qs('#purchaseMeta').textContent = `SKU: ${product.sku} | 数量: ${codes.length}`;
      qs('#successModal').classList.remove('hidden');

    } catch (e) {
      toast({ title: '购买失败', message: formatError(e), type: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = '确认购买';
    }
  }

  // 加载购买历史
  async function loadHistory() {
    try {
      const txs = await apiRequest('/wallet/transactions?limit=10');
      const purchaseTxs = txs.filter(t => t.kind === 'purchase').slice(0, 5);

      if (purchaseTxs.length === 0) {
        qs('#historyList').innerHTML = '<div class="muted-2" style="text-align: center; padding: 20px;">暂无购买记录</div>';
        return;
      }

      qs('#historyList').innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>时间</th>
              <th>产品</th>
              <th>金额</th>
              <th>余额</th>
            </tr>
          </thead>
          <tbody>
            ${purchaseTxs.map(t => `
              <tr>
                <td>${esc(t.created_at || '')}</td>
                <td>卡密购买</td>
                <td style="color: var(--danger);">-${moneyFromCents(t.amount_cents, t.currency)}</td>
                <td>${moneyFromCents(t.balance_after_cents, t.currency)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      console.error('Failed to load history', e);
    }
  }

  // 初始化
  initTheme();
  qs('#themeToggleBtn').addEventListener('click', toggleTheme);

  // 供应商切换
  qsa('.provider-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      qsa('.provider-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.currentProvider = tab.dataset.provider;
      renderProducts();
    });
  });

  // 确认弹窗按钮
  qs('#cancelPurchaseBtn').addEventListener('click', hideConfirmModal);
  qs('#confirmPurchaseBtn').addEventListener('click', purchaseCard);
  qs('#confirmModal').addEventListener('click', (e) => {
    if (e.target === qs('#confirmModal')) hideConfirmModal();
  });

  // 成功弹窗按钮
  qs('#closeSuccessBtn').addEventListener('click', () => {
    qs('#successModal').classList.add('hidden');
    loadHistory();
  });

  async function copyToClipboard(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    if (!ok) throw new Error('复制失败');
  }

  function downloadTextFile(text, filename) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function buildExportFilename() {
    const sku = String(state.lastPurchase?.sku || 'cards').replace(/[^a-zA-Z0-9_-]+/g, '_');
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    return `${sku}_${ts}.txt`;
  }

  qs('#copyCardCodesBtn').addEventListener('click', async () => {
    const text = state.lastPurchase?.codesText || '';
    if (!text) {
      toast({ title: '暂无内容', message: '没有可复制的卡密内容', type: 'error' });
      return;
    }
    try {
      await copyToClipboard(text);
      toast({ title: '复制成功', message: '卡密已复制到剪贴板', type: 'success' });
    } catch (e) {
      toast({ title: '复制失败', message: formatError(e), type: 'error' });
    }
  });

  qs('#exportCardCodesBtn').addEventListener('click', () => {
    const text = state.lastPurchase?.codesText || '';
    if (!text) {
      toast({ title: '暂无内容', message: '没有可导出的卡密内容', type: 'error' });
      return;
    }
    try {
      downloadTextFile(text, buildExportFilename());
      toast({ title: '已导出', message: '已生成 TXT 文件', type: 'success' });
    } catch (e) {
      toast({ title: '导出失败', message: formatError(e), type: 'error' });
    }
  });

  // 刷新历史
  qs('#refreshHistoryBtn').addEventListener('click', () => {
    loadHistory();
    toast({ title: '已刷新', message: '购买记录已更新', type: 'success' });
  });

  // 初始化加载
  (async () => {
    await requireAuth();
    await loadWallet();
    await loadProducts();
    await loadHistory();
  })().catch(e => {
    toast({ title: '初始化失败', message: formatError(e), type: 'error' });
  });
})();

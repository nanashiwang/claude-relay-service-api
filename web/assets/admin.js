(function () {
  const { qs, qsa, apiRequest, toast, formatError, moneyFromCents, pretty, escapeHtml: esc } = window.App;

  const state = {
    currentPage: 'dashboard',
    currentPeriod: 'today',
    me: null,
    epayConfig: null,
    announcement: null
  };

  // === 页面导航 ===
  function setPage(name) {
    state.currentPage = name;

    // 更新导航状态
    qsa('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.page === name);
    });

    // 更新页面显示
    qsa('.admin-page').forEach(page => {
      page.classList.toggle('active', page.id === `page-${name}`);
    });

    // 自动加载对应数据
    loadPageData(name);
  }

  async function loadPageData(page) {
    switch (page) {
      case 'dashboard':
        await loadDashboard();
        break;
      case 'products':
        await loadProducts();
        break;
      case 'cards':
        await loadProductsForFilter();
        break;
      case 'orders':
        await loadOrders();
        break;
      case 'users':
        await loadUsers();
        break;
      case 'apikeys':
        await loadApiKeys();
        break;
      case 'payments':
        await loadEpayConfig();
        break;
      case 'announcement':
        await loadAnnouncementConfig();
        break;
    }
  }

  // === 权限检查 ===
  async function checkAdmin() {
    try {
      state.me = await apiRequest('/auth/me');
      if (!state.me.is_admin) {
        window.location.href = '/web/dashboard.html';
        return false;
      }
      return true;
    } catch {
      window.location.href = '/';
      return false;
    }
  }

  // === 数据概览 ===
  async function loadDashboard() {
    try {
      // 加载统计数据
      const stats = await Promise.allSettled([
        apiRequest('/admin/stats').catch(() => null),
        apiRequest('/orders?limit=10')
      ]);

      // 处理统计
      if (stats[0].status === 'fulfilled' && stats[0].value) {
        const s = stats[0].value;
        qs('#statUsers').textContent = s.total_users ?? '-';
        qs('#statOrders').textContent = s.total_orders ?? '-';
        qs('#statRevenue').textContent =
          s.total_revenue === undefined || s.total_revenue === null ? '-' : moneyFromCents(s.total_revenue, 'CNY');
        qs('#statCards').textContent = s.total_cards ?? '-';
      }

      // 处理最近订单
      if (stats[1].status === 'fulfilled') {
        renderRecentOrders(stats[1].value);
      }

    } catch (e) {
      console.error('Failed to load dashboard', e);
    }
  }

  function renderRecentOrders(orders) {
    const wrap = qs('#recentOrdersPreview');
    if (!orders || orders.length === 0) {
      wrap.innerHTML = '<div class="muted-2">暂无订单</div>';
      return;
    }
    wrap.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>用户</th>
            <th>产品</th>
            <th>金额</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          ${orders.slice(0, 5).map(order => `
            <tr>
              <td>${esc(order.user_id || '')}</td>
              <td>${esc(order.product_sku || '-')}</td>
              <td>${order.price_cents ? moneyFromCents(order.price_cents, order.currency) : '-'}</td>
              <td>${esc(order.created_at || '')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  // === 产品管理 ===
  function normalizeTierDiscounts(tiers) {
    if (!Array.isArray(tiers)) return [];
    const normalized = [];
    const seen = new Set();
    for (const item of tiers) {
      const minQuantity = parseInt(item?.min_quantity, 10);
      const discountPercent = parseInt(item?.discount_percent, 10);
      if (!Number.isFinite(minQuantity) || minQuantity <= 0) continue;
      if (!Number.isFinite(discountPercent) || discountPercent <= 0 || discountPercent >= 100) continue;
      if (seen.has(minQuantity)) continue;
      seen.add(minQuantity);
      normalized.push({ min_quantity: minQuantity, discount_percent: discountPercent });
    }
    normalized.sort((a, b) => a.min_quantity - b.min_quantity);
    return normalized;
  }

  function formatTierDiscountsValue(tiers) {
    const normalized = normalizeTierDiscounts(tiers);
    if (!normalized.length) return '';
    return normalized.map((tier) => `${tier.min_quantity}:${tier.discount_percent}`).join(',');
  }

  function parseTierDiscountsInput(raw) {
    const text = String(raw || '').trim();
    if (!text) return [];

    const items = text.split(',').map((item) => item.trim()).filter(Boolean);
    const parsed = [];
    const seen = new Set();
    for (const item of items) {
      const parts = item.split(':').map((part) => part.trim());
      if (parts.length !== 2) {
        throw new Error(`阶梯折扣格式错误: ${item}`);
      }

      const minQuantity = Number(parts[0]);
      const discountPercent = Number(parts[1]);
      if (!Number.isInteger(minQuantity) || minQuantity <= 0) {
        throw new Error(`阶梯数量必须是正整数: ${parts[0]}`);
      }
      if (!Number.isInteger(discountPercent) || discountPercent <= 0 || discountPercent >= 100) {
        throw new Error(`折扣必须是 1-99 的整数: ${parts[1]}`);
      }
      if (seen.has(minQuantity)) {
        throw new Error(`阶梯数量重复: ${minQuantity}`);
      }
      seen.add(minQuantity);
      parsed.push({ min_quantity: minQuantity, discount_percent: discountPercent });
    }

    parsed.sort((a, b) => a.min_quantity - b.min_quantity);
    return parsed;
  }

  async function loadProducts() {
    const wrap = qs('#productList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      const products = await apiRequest('/products');

      if (!products || products.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">📦</div><div class="text">暂无产品</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>SKU</th>
              <th>名称</th>
              <th>原价</th>
              <th>折扣(%)</th>
              <th>阶梯折扣</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${products.map(p => `
              <tr>
                <td>${esc(p.id)}</td>
                <td>${esc(p.sku)}</td>
                <td>${esc(p.name)}</td>
                <td>${moneyFromCents(p.price_cents, p.currency)}</td>
                <td>${p.discount_percent ? `${esc(p.discount_percent)}%` : '-'}</td>
                <td>${esc(formatTierDiscountsValue(p.tier_discounts) || '-')}</td>
                <td>${p.active ? '<span class="badge success">上架</span>' : '<span class="badge">下架</span>'}</td>
                <td>
                  <button class="btn small" data-action="edit-product" data-id="${esc(p.id)}" data-sku="${esc(p.sku)}" data-name="${esc(p.name)}" data-price="${esc(p.price_cents)}" data-discount="${esc(p.discount_percent ?? '')}" data-tiers="${esc(formatTierDiscountsValue(p.tier_discounts))}" data-active="${p.active ? 'true' : 'false'}">编辑</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      wrap.innerHTML = `<div class="muted-2">加载失败：${esc(formatError(e))}</div>`;
    }
  }

  async function updateProduct() {
    const productId = Number(qs('#editProductId').value || '0');
    if (!productId) {
      toast({ title: '参数错误', message: '请输入产品 ID', type: 'error' });
      return;
    }

    const priceYuanText = (qs('#editProductPrice').value || '').trim();
    let priceCents = undefined;
    if (priceYuanText !== '') {
      const num = Number(priceYuanText);
      if (!Number.isFinite(num) || num < 0) {
        toast({ title: '参数错误', message: '价格请输入有效数字（元）', type: 'error' });
        return;
      }
      priceCents = Math.round(num * 100);
    }

    const discountPercentText = (qs('#editProductDiscountPercent').value || '').trim();
    let discountPercent = undefined;
    if (discountPercentText !== '') {
      const num = Number(discountPercentText);
      if (!Number.isFinite(num) || num < 0 || num > 100 || !Number.isInteger(num)) {
        toast({ title: '参数错误', message: '折扣请输入 0-100 的整数百分比', type: 'error' });
        return;
      }
      if (num === 0 || num >= 100) {
        discountPercent = null;
      } else {
        discountPercent = num;
      }
    }

    let tierDiscounts = [];
    try {
      tierDiscounts = parseTierDiscountsInput(qs('#editProductTierDiscounts').value);
    } catch (e) {
      toast({ title: '参数错误', message: formatError(e), type: 'error' });
      return;
    }

    const payload = {
      name: (qs('#editProductName').value || '').trim() || undefined,
      price_cents: priceCents,
      discount_percent: discountPercent,
      tier_discounts: tierDiscounts,
      active: qs('#editProductActive').value === '' ? undefined : qs('#editProductActive').value === 'true',
    };

    const outEl = qs('#updateProductOut');
    outEl.textContent = '请求中...';

    try {
      const data = await apiRequest(`/products/${productId}`, { method: 'PATCH', body: payload });
      outEl.textContent = pretty(data);
      toast({ title: '已更新产品', message: data.sku || '', type: 'success' });
      await loadProducts();
    } catch (e) {
      outEl.textContent = '错误：' + formatError(e);
      toast({ title: '更新失败', message: formatError(e), type: 'error' });
    }
  }

  function fillProductForm(id, sku, name, price, discountPercent, tierDiscountsText, active) {
    qs('#editProductId').value = id;
    qs('#editProductName').value = name;
    qs('#editProductPrice').value = (Number(price || 0) / 100).toFixed(2);
    qs('#editProductDiscountPercent').value = discountPercent ? String(discountPercent) : '';
    qs('#editProductTierDiscounts').value = tierDiscountsText || '';
    qs('#editProductActive').value = active ? 'true' : 'false';
  }

  // === 卡密管理 ===
  async function importCards() {
    const sku = (qs('#importSku').value || '').trim();
    const fileEl = qs('#importFile');
    const f = fileEl.files && fileEl.files[0];

    if (!sku) {
      toast({ title: '参数错误', message: '请选择产品', type: 'error' });
      return;
    }
    if (!f) {
      toast({ title: '参数错误', message: '请选择 txt 文件', type: 'error' });
      return;
    }

    const outEl = qs('#importOut');
    outEl.textContent = '上传中...';

    try {
      const form = new FormData();
      form.append('product_sku', sku);
      form.append('file', f);
      const data = await apiRequest('/admin/cards/import', { method: 'POST', body: form });
      outEl.textContent = pretty(data);
      toast({ title: '导入完成', message: `成功 ${data.inserted}，跳过 ${data.skipped}`, type: 'success' });
    } catch (e) {
      outEl.textContent = '错误：' + formatError(e);
      toast({ title: '导入失败', message: formatError(e), type: 'error' });
    }
  }

  async function checkInventory() {
    const sku = (qs('#inventorySku').value || '').trim();
    if (!sku) {
      toast({ title: '参数错误', message: '请选择产品', type: 'error' });
      return;
    }

    const outEl = qs('#inventoryOut');
    outEl.textContent = '查询中...';

    try {
      const data = await apiRequest(`/admin/inventory/${encodeURIComponent(sku)}`);
      outEl.textContent = pretty(data);
    } catch (e) {
      outEl.textContent = '错误：' + formatError(e);
    }
  }

  async function loadProductsForFilter() {
    try {
      const products = await apiRequest('/products');

      const byProvider = new Map();
      for (const p of products || []) {
        const key = String(p.provider || '').toLowerCase();
        if (!byProvider.has(key)) byProvider.set(key, []);
        byProvider.get(key).push(p);
      }

      const providerOrder = ['codex', 'gemini', 'claude'];
      const providerKeys = Array.from(byProvider.keys()).sort((a, b) => a.localeCompare(b, 'en'));
      const ordered = providerOrder.filter(k => byProvider.has(k)).concat(providerKeys.filter(k => !providerOrder.includes(k)));

      const optionHtml = ordered.map((provider) => {
        const list = byProvider.get(provider) || [];
        const label = provider ? provider.toUpperCase() : '其他';
        const opts = list.map((p) => `<option value="${esc(p.sku)}">${esc(p.name)} (${esc(p.sku)})</option>`).join('');
        return `<optgroup label="${esc(label)}">${opts}</optgroup>`;
      }).join('');

      const select = qs('#cardProductFilter');
      if (select) {
        select.innerHTML = '<option value="">全部产品</option>' + optionHtml;
      }

      const importSel = qs('#importSku');
      if (importSel && importSel.tagName === 'SELECT') {
        importSel.innerHTML = '<option value="">请选择产品</option>' + optionHtml;
      }

      const inventorySel = qs('#inventorySku');
      if (inventorySel && inventorySel.tagName === 'SELECT') {
        inventorySel.innerHTML = '<option value="">请选择产品</option>' + optionHtml;
      }
    } catch (e) {
      console.error('Failed to load products', e);
    }
  }

  async function loadCards() {
    const wrap = qs('#cardsList');
    const sku = qs('#cardProductFilter').value || undefined;
    const status = qs('#cardStatusFilter').value || undefined;

    let url = '/admin/cards?limit=500';
    const params = [];
    if (sku) params.push(`product_sku=${encodeURIComponent(sku)}`);
    if (status) params.push(`status=${status}`);
    if (params.length) url += '&' + params.join('&');

    wrap.innerHTML = '<div class="muted-2">查询中...</div>';

    try {
      const cards = await apiRequest(url);

      if (!cards || cards.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">💳</div><div class="text">暂无卡密</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>卡密</th>
              <th>产品</th>
              <th>状态</th>
              <th>订单ID</th>
              <th>过期时间</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            ${cards.map(c => `
              <tr>
                <td style="font-family:var(--mono);font-size:11px;">${esc(c.code?.substring(0, 16))}...</td>
                <td>${esc(c.product_sku || '-')}</td>
                <td>${renderCardStatus(c.status)}</td>
                <td>${esc(c.order_id?.toString() || '-')}</td>
                <td>${esc(c.expires_at || '-')}</td>
                <td>${esc(c.created_at || '-')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      wrap.innerHTML = `<div class="muted-2">查询失败：${esc(formatError(e))}</div>`;
    }
  }

  function renderCardStatus(status) {
    const badges = {
      available: '<span class="badge success">可用</span>',
      claimed: '<span class="badge warn">已提取</span>',
      voided: '<span class="badge">作废</span>'
    };
    return badges[status] || `<span class="badge">${esc(status)}</span>`;
  }

  // === 订单记录 ===
  async function loadOrders(period = 'today') {
    const wrap = qs('#ordersList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      let url = '/orders?limit=100';
      // 这里可以根据 period 添加时间筛选参数（如果后端支持）
      const items = await apiRequest(url);

      if (!items || items.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">📦</div><div class="text">暂无订单</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户ID</th>
              <th>产品SKU</th>
              <th>价格</th>
              <th>卡密</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(order => `
              <tr>
                <td>${esc(order.id)}</td>
                <td>${esc(order.user_id?.toString() || '-')}</td>
                <td>${esc(order.product_sku || '-')}</td>
                <td>${order.price_cents ? moneyFromCents(order.price_cents, order.currency) : '-'}</td>
                <td style="font-family:var(--mono);font-size:11px;">${esc(order.card_code?.substring(0, 12) || '-')}${order.card_code ? '...' : ''}</td>
                <td>${esc(order.created_at || '-')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      wrap.innerHTML = `<div class="muted-2">加载失败：${esc(formatError(e))}</div>`;
    }
  }

  // === 用户管理 ===
  async function loadUsers() {
    const wrap = qs('#usersList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      const users = await apiRequest('/admin/users');

      if (!users || users.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">👥</div><div class="text">暂无用户</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>管理员</th>
              <th>状态</th>
              <th>余额</th>
              <th>注册时间</th>
            </tr>
          </thead>
          <tbody>
            ${users.map(u => `
              <tr>
                <td>${esc(u.id)}</td>
                <td>${esc(u.username)}</td>
                <td>${u.is_admin ? '<span class="badge primary">是</span>' : '<span class="badge">否</span>'}</td>
                <td>${u.is_active ? '<span class="badge success">正常</span>' : '<span class="badge danger">禁用</span>'}</td>
                <td>${u.balance_cents !== undefined ? moneyFromCents(u.balance_cents, u.currency || 'CNY') : '-'}</td>
                <td>${esc(u.created_at || '-')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      wrap.innerHTML = `<div class="muted-2">加载失败：${esc(formatError(e))}</div>`;
    }
  }

  // === API Key 管理 ===
  async function loadApiKeys() {
    const wrap = qs('#apiKeysList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      const keys = await apiRequest('/admin/api-keys');

      if (!keys || keys.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">🔑</div><div class="text">暂无 API Key</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户ID</th>
              <th>名称</th>
              <th>Key</th>
              <th>状态</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            ${keys.map(k => `
              <tr>
                <td>${esc(k.id)}</td>
                <td>${esc(k.user_id?.toString() || '-')}</td>
                <td>${esc(k.name || '-')}</td>
                <td style="font-family:var(--mono);font-size:11px;">${esc(k.key_prefix || '')}***</td>
                <td>${k.is_active ? '<span class="badge success">正常</span>' : '<span class="badge danger">禁用</span>'}</td>
                <td>${esc(k.created_at || '-')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      wrap.innerHTML = `<div class="muted-2">加载失败：${esc(formatError(e))}</div>`;
    }
  }

  async function createApiKey() {
    const userId = Number(qs('#apiKeyUserId').value || '0');
    const name = (qs('#apiKeyName').value || '').trim();

    if (!userId) {
      toast({ title: '参数错误', message: '请输入用户 ID', type: 'error' });
      return;
    }

    const outEl = qs('#apiKeyOut');
    outEl.textContent = '创建中...';

    try {
      const path = `/admin/users/${userId}/api-keys${name ? `?name=${encodeURIComponent(name)}` : ''}`;
      const data = await apiRequest(path, { method: 'POST' });
      outEl.textContent = pretty(data);
      toast({ title: '已生成 API Key', message: '请妥善保存，仅展示一次', type: 'success' });
      await loadApiKeys();
    } catch (e) {
      outEl.textContent = '错误：' + formatError(e);
      toast({ title: '生成失败', message: formatError(e), type: 'error' });
    }
  }

  // === 在线支付（易支付）配置 ===
  function textOrNull(value) {
    const text = String(value || '').trim();
    return text ? text : null;
  }

  function fillEpayForm(config) {
    const data = config || {};
    qs('#epayBaseUrl').value = data.base_url || '';
    qs('#epayPid').value = data.pid || '';
    qs('#epayKey').value = data.merchant_key || '';
    qs('#epaySignType').value = (data.sign_type || 'MD5').toUpperCase();
    qs('#epayPublicBaseUrl').value = data.public_base_url || '';
    qs('#epayNotifyUrl').value = data.notify_url || '';
    qs('#epayReturnUrl').value = data.return_url || '';
    qs('#epayActive').value = data.active === false ? 'false' : 'true';
  }

  async function loadEpayConfig() {
    try {
      const data = await apiRequest('/payment-configs/epay');
      state.epayConfig = data || null;
      fillEpayForm(state.epayConfig);
    } catch (e) {
      toast({ title: '加载在线支付配置失败', message: formatError(e), type: 'error' });
    }
  }

  async function saveEpayConfig() {
    const payload = {
      base_url: String(qs('#epayBaseUrl').value || '').trim(),
      pid: String(qs('#epayPid').value || '').trim(),
      merchant_key: String(qs('#epayKey').value || '').trim(),
      sign_type: String(qs('#epaySignType').value || 'MD5').trim().toUpperCase(),
      public_base_url: textOrNull(qs('#epayPublicBaseUrl').value),
      notify_url: textOrNull(qs('#epayNotifyUrl').value),
      return_url: textOrNull(qs('#epayReturnUrl').value),
      active: qs('#epayActive').value === 'true',
    };

    if (!payload.base_url || !payload.pid || !payload.merchant_key) {
      toast({ title: '参数错误', message: '请填写网关地址、商户ID、商户密钥', type: 'error' });
      return;
    }

    try {
      const data = await apiRequest('/payment-configs/epay', { method: 'PUT', body: payload });
      state.epayConfig = data || null;
      fillEpayForm(state.epayConfig);
      toast({ title: '在线支付配置已保存', message: '', type: 'success' });
    } catch (e) {
      toast({ title: '保存在线支付配置失败', message: formatError(e), type: 'error' });
    }
  }

  // === 公告配置 ===
  let announcementQrObjectUrl = null;
  let announcementQrUrl = '';

  function setAnnouncementQrPreview(url, { persist = true } = {}) {
    const img = qs('#announcementQrPreview');
    const empty = qs('#announcementQrPreviewEmpty');
    if (persist) announcementQrUrl = url || '';
    if (!img || !empty) return;

    if (!url) {
      img.style.display = 'none';
      img.removeAttribute('src');
      empty.style.display = 'block';
      return;
    }

    img.src = url;
    img.style.display = 'block';
    empty.style.display = 'none';
  }

  async function uploadAnnouncementQr() {
    const fileEl = qs('#announcementQrFile');
    const f = fileEl && fileEl.files && fileEl.files[0];
    if (!f) {
      toast({ title: '参数错误', message: '请选择图片文件', type: 'error' });
      return;
    }
    if (f.type && !f.type.startsWith('image/')) {
      toast({ title: '文件类型错误', message: '仅支持图片文件', type: 'error' });
      return;
    }

    const btn = qs('#uploadAnnouncementQrBtn');
    const oldText = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '上传中...';
    }

    try {
      const form = new FormData();
      form.append('file', f);
      const data = await apiRequest('/announcement/upload-qr', { method: 'POST', body: form });
      const url = data && data.url ? String(data.url) : '';
      if (!url) throw new Error('上传失败：未返回 url');

      if (announcementQrObjectUrl) {
        URL.revokeObjectURL(announcementQrObjectUrl);
        announcementQrObjectUrl = null;
      }

      setAnnouncementQrPreview(url);
      toast({ title: '上传成功', message: '公告二维码已更新', type: 'success' });
    } catch (e) {
      toast({ title: '上传失败', message: formatError(e), type: 'error' });
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = oldText || '上传二维码';
      }
    }
  }

  function fillAnnouncementForm(data) {
    if (!data) return;
    const idEl = qs('#announcementId');
    if (idEl) idEl.value = data.id || '';
    qs('#announcementTitle').value = data.title || '';
    qs('#announcementContent').value = data.content || '';
    qs('#announcementActive').value = data.active ? 'true' : 'false';
    setAnnouncementQrPreview(data.group_qr_url || '');

    const fileEl = qs('#announcementQrFile');
    if (fileEl) fileEl.value = '';
    if (announcementQrObjectUrl) {
      URL.revokeObjectURL(announcementQrObjectUrl);
      announcementQrObjectUrl = null;
    }
  }

  async function loadAnnouncementConfig() {
    const titleEl = qs('#announcementTitle');
    const contentEl = qs('#announcementContent');
    if (!titleEl || !contentEl) return;

    try {
      const data = await apiRequest('/announcement');
      state.announcement = data;
      fillAnnouncementForm(data);
    } catch (e) {
      toast({ title: '加载失败', message: formatError(e), type: 'error' });
    }
  }

  async function saveAnnouncementConfig() {
    const payload = {
      title: (qs('#announcementTitle').value || '').trim(),
      content: qs('#announcementContent').value || '',
      group_qr_url: announcementQrUrl || null,
      active: qs('#announcementActive').value === 'true',
    };

    if (!payload.title) {
      toast({ title: '参数错误', message: '公告标题不能为空', type: 'error' });
      return;
    }
    if (!payload.content.trim()) {
      toast({ title: '参数错误', message: '公告内容不能为空', type: 'error' });
      return;
    }

    try {
      const data = await apiRequest('/announcement', { method: 'PATCH', body: payload });
      state.announcement = data;
      fillAnnouncementForm(data);
      toast({ title: '保存成功', message: '', type: 'success' });
    } catch (e) {
      toast({ title: '保存失败', message: formatError(e), type: 'error' });
    }
  }

  // === 事件绑定 ===
  function bindEvents() {
    const bindClick = (selector, handler) => {
      const el = qs(selector);
      if (el) el.addEventListener('click', handler);
      return el;
    };

    // 导航
    qsa('.nav-item').forEach(item => {
      item.addEventListener('click', () => setPage(item.dataset.page));
    });

    // 菜单切换（移动端）
    bindClick('#menuToggle', () => {
      const sidebar = qs('#sidebar');
      if (sidebar) sidebar.classList.toggle('open');
    });

    // 数据概览刷新
    bindClick('#refreshDashboard', () => loadDashboard());

    // 产品管理
    bindClick('#loadProductsBtn', () => loadProducts());
    bindClick('#updateProductBtn', updateProduct);
    const productList = qs('#productList');
    if (productList) {
      productList.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action="edit-product"]');
        if (!btn) return;
        const id = Number(btn.dataset.id || '0');
        if (!id) return;
        fillProductForm(
          id,
          btn.dataset.sku || '',
          btn.dataset.name || '',
          Number(btn.dataset.price || '0'),
          btn.dataset.discount || '',
          btn.dataset.tiers || '',
          btn.dataset.active === 'true',
        );
      });
    }

    // 卡密管理
    bindClick('#importCardsBtn', importCards);
    bindClick('#inventoryBtn', checkInventory);
    bindClick('#loadCardsBtn', loadCards);

    // 订单记录
    bindClick('#loadOrdersBtn', () => loadOrders(state.currentPeriod));
    qsa('#page-orders .filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        qsa('#page-orders .filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentPeriod = btn.dataset.period;
        loadOrders(state.currentPeriod);
      });
    });

    // 用户管理
    bindClick('#loadUsersBtn', () => loadUsers());

    // API Key
    bindClick('#loadApiKeysBtn', () => loadApiKeys());
    bindClick('#createApiKeyBtn', createApiKey);

    // 支付配置
    bindClick('#loadPaymentsBtn', loadEpayConfig);
    bindClick('#saveEpayConfigBtn', saveEpayConfig);
    bindClick('#resetEpayConfigBtn', loadEpayConfig);

    // 公告配置
    bindClick('#loadAnnouncementBtn', () => loadAnnouncementConfig());
    bindClick('#saveAnnouncementBtn', saveAnnouncementConfig);
    bindClick('#uploadAnnouncementQrBtn', uploadAnnouncementQr);

    const announcementQrFileEl = qs('#announcementQrFile');
    if (announcementQrFileEl) {
      announcementQrFileEl.addEventListener('change', () => {
        if (announcementQrObjectUrl) {
          URL.revokeObjectURL(announcementQrObjectUrl);
          announcementQrObjectUrl = null;
        }
        const f = announcementQrFileEl.files && announcementQrFileEl.files[0];
        if (!f) {
          setAnnouncementQrPreview('');
          return;
        }
        announcementQrObjectUrl = URL.createObjectURL(f);
        setAnnouncementQrPreview(announcementQrObjectUrl, { persist: false });
      });
    }
  }

  // === 初始化 ===
  (async () => {
    const isAdmin = await checkAdmin();
    if (!isAdmin) return;

    bindEvents();
    await loadDashboard();
  })().catch(e => {
    toast({ title: '初始化失败', message: formatError(e), type: 'error' });
  });
})();

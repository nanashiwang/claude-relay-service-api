(function () {
  const { qs, qsa, apiRequest, toast, formatError, moneyFromCents, pretty, escapeHtml: esc } = window.App;

  const DEFAULT_RECHARGE_REJECT_NOTE = '未收到转账信息，如有疑问请联系qq：438274867';

  const state = {
    currentPage: 'dashboard',
    currentFilter: 'pending',
    currentPeriod: 'today',
    reviewRequest: null,
    me: null,
    paymentConfigsById: {},
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
      case 'recharges':
        await loadRecharges();
        break;
      case 'refunds':
        await loadRefunds();
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
        await loadPaymentConfigs();
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
        apiRequest('/admin/recharge-requests?status=pending&limit=5'),
        apiRequest('/admin/refund-requests?status=pending&limit=5'),
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

      // 处理待处理充值
      if (stats[1].status === 'fulfilled') {
        const recharges = stats[1].value;
        qs('#pendingRechargeBadge').textContent = recharges.length;
        qs('#rechargeCount').textContent = recharges.length;
        renderPendingRechargePreview(recharges);
      }

      // 处理待处理退款
      if (stats[2].status === 'fulfilled') {
        const refunds = stats[2].value;
        qs('#pendingRefundBadge').textContent = refunds.length;
        qs('#refundCount').textContent = refunds.length;
        renderPendingRefundPreview(refunds);
      }

      // 处理最近订单
      if (stats[3].status === 'fulfilled') {
        renderRecentOrders(stats[3].value);
      }

    } catch (e) {
      console.error('Failed to load dashboard', e);
    }
  }

  function renderPendingRechargePreview(items) {
    const wrap = qs('#pendingRechargePreview');
    if (!items || items.length === 0) {
      wrap.innerHTML = '<div class="muted-2">暂无待处理</div>';
      return;
    }
    wrap.innerHTML = `
      <table class="table">
        <tbody>
          ${items.slice(0, 3).map(item => `
            <tr>
              <td>${esc(item.user_id || '')}</td>
              <td>${moneyFromCents(item.amount_cents, item.currency)}</td>
              <td>${esc(item.payment_method || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${items.length > 3 ? '<div class="muted-2" style="font-size:11px;margin-top:8px;">还有 ' + (items.length - 3) + ' 条...</div>' : ''}
    `;
  }

  function renderPendingRefundPreview(items) {
    const wrap = qs('#pendingRefundPreview');
    if (!items || items.length === 0) {
      wrap.innerHTML = '<div class="muted-2">暂无待处理</div>';
      return;
    }
    wrap.innerHTML = `
      <table class="table">
        <tbody>
          ${items.slice(0, 3).map(item => `
            <tr>
              <td>${esc(item.user_id || '')}</td>
              <td>${moneyFromCents(item.amount_cents, item.currency)}</td>
              <td>${esc(item.reason?.substring(0, 20) || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${items.length > 3 ? '<div class="muted-2" style="font-size:11px;margin-top:8px;">还有 ' + (items.length - 3) + ' 条...</div>' : ''}
    `;
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

  // === 充值审核 ===
  async function loadRecharges(status = 'pending') {
    const wrap = qs('#rechargeList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      const url = status === 'all'
        ? '/admin/recharge-requests?limit=100'
        : `/admin/recharge-requests?status=${status}&limit=100`;
      const items = await apiRequest(url);

      if (!items || items.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">📋</div><div class="text">暂无数据</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户ID</th>
              <th>金额</th>
              <th>支付方式</th>
              <th>备注</th>
              <th>状态</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(item => `
              <tr>
                <td>${esc(item.id)}</td>
                <td>${esc(item.user_id || '')}</td>
                <td>${moneyFromCents(item.amount_cents, item.currency)}</td>
                <td>${esc(item.payment_method || '-')}</td>
                <td>${esc(item.payment_reference || '-')}</td>
                <td>${renderStatusBadge(item.status)}</td>
                <td>${esc(item.created_at || '')}</td>
                <td>
                  ${item.status === 'pending' ? `
                    <button class="btn small success" data-action="review-recharge" data-id="${esc(item.id)}" data-review="approve">通过</button>
                    <button class="btn small danger" data-action="review-recharge" data-id="${esc(item.id)}" data-review="reject">拒绝</button>
                  ` : '-'}
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

  // === 退款审核 ===
  async function loadRefunds(status = 'pending') {
    const wrap = qs('#refundList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      const url = status === 'all'
        ? '/admin/refund-requests?limit=100'
        : `/admin/refund-requests?status=${status}&limit=100`;
      const items = await apiRequest(url);

      if (!items || items.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">📋</div><div class="text">暂无数据</div></div>';
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户ID</th>
              <th>金额</th>
              <th>原因</th>
              <th>状态</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(item => `
              <tr>
                <td>${esc(item.id)}</td>
                <td>${esc(item.user_id || '')}</td>
                <td>${moneyFromCents(item.amount_cents, item.currency)}</td>
                <td title="${esc(item.reason || '')}">${esc(item.reason?.substring(0, 30) || '-')}...</td>
                <td>${renderStatusBadge(item.status)}</td>
                <td>${esc(item.created_at || '')}</td>
                <td>
                  ${item.status === 'pending' ? `
                    <button class="btn small success" data-action="review-refund" data-id="${esc(item.id)}" data-review="approve">通过</button>
                    <button class="btn small danger" data-action="review-refund" data-id="${esc(item.id)}" data-review="reject">拒绝</button>
                  ` : '-'}
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

  function renderStatusBadge(status) {
    const badges = {
      pending: '<span class="badge warn">pending</span>',
      approved: '<span class="badge success">approved</span>',
      rejected: '<span class="badge danger">rejected</span>',
      canceled: '<span class="badge">canceled</span>'
    };
    return badges[status] || `<span class="badge">${esc(status)}</span>`;
  }

  // === 产品管理 ===
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
                <td>${p.active ? '<span class="badge success">上架</span>' : '<span class="badge">下架</span>'}</td>
                <td>
                  <button class="btn small" data-action="edit-product" data-id="${esc(p.id)}" data-sku="${esc(p.sku)}" data-name="${esc(p.name)}" data-price="${esc(p.price_cents)}" data-discount="${esc(p.discount_percent ?? '')}" data-active="${p.active ? 'true' : 'false'}">编辑</button>
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

    const payload = {
      name: (qs('#editProductName').value || '').trim() || undefined,
      price_cents: priceCents,
      discount_percent: discountPercent,
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

  function fillProductForm(id, sku, name, price, discountPercent, active) {
    qs('#editProductId').value = id;
    qs('#editProductName').value = name;
    qs('#editProductPrice').value = (Number(price || 0) / 100).toFixed(2);
    qs('#editProductDiscountPercent').value = discountPercent ? String(discountPercent) : '';
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

  // === 支付配置 ===
  let paymentQrObjectUrl = null;

  function setPaymentQrPreview(url) {
    const img = qs('#paymentQrPreview');
    const empty = qs('#paymentQrPreviewEmpty');
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

  function extractFirstImgSrc(html) {
    const text = String(html || '');
    const m = text.match(/<img[^>]+src=["']([^"']+)["'][^>]*>/i);
    return m ? m[1] : '';
  }

  function upsertFirstImgSrc(html, url) {
    const text = String(html || '');
    const re = /<img([^>]+)src=["']([^"']+)["']([^>]*)>/i;
    if (re.test(text)) {
      return text.replace(re, (_all, pre, _old, post) => `<img${pre}src="${url}"${post}>`);
    }

    const imgTag = `<img src="${url}" alt="收款码" style="max-width:280px;width:100%;height:auto;border-radius:12px;border:1px solid var(--border);" />`;
    const block = `<div style="margin-top:12px">${imgTag}</div>`;
    return (text.trim() ? text.trim() + '\n' : '') + block;
  }

  async function uploadPaymentQr() {
    const fileEl = qs('#paymentQrFile');
    const f = fileEl && fileEl.files && fileEl.files[0];
    if (!f) {
      toast({ title: '参数错误', message: '请选择图片文件', type: 'error' });
      return;
    }
    if (f.type && !f.type.startsWith('image/')) {
      toast({ title: '文件类型错误', message: '仅支持图片文件', type: 'error' });
      return;
    }

    const btn = qs('#uploadPaymentQrBtn');
    const oldText = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '上传中...';
    }

    try {
      const form = new FormData();
      form.append('file', f);
      const data = await apiRequest('/payment-configs/upload-qr', { method: 'POST', body: form });
      const url = data && data.url ? String(data.url) : '';
      if (!url) throw new Error('上传失败：未返回 url');

      if (paymentQrObjectUrl) {
        URL.revokeObjectURL(paymentQrObjectUrl);
        paymentQrObjectUrl = null;
      }

      setPaymentQrPreview(url);

      const ta = qs('#paymentAccountInfo');
      if (ta) ta.value = upsertFirstImgSrc(ta.value, url);

      toast({ title: '上传成功', message: '已插入到“收款账号信息”', type: 'success' });
    } catch (e) {
      toast({ title: '上传失败', message: formatError(e), type: 'error' });
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = oldText || '上传收款码';
      }
    }
  }

  async function loadPaymentConfigs() {
    const wrap = qs('#paymentsList');
    wrap.innerHTML = '<div class="muted-2">加载中...</div>';

    try {
      const configs = await apiRequest('/payment-configs');
      state.paymentConfigsById = {};
      for (const c of (configs || [])) {
        if (c && typeof c.id !== 'undefined') state.paymentConfigsById[String(c.id)] = c;
      }

      if (!configs || configs.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><div class="icon">💳</div><div class="text">暂无支付配置</div></div>';
        clearPaymentForm();
        return;
      }

      wrap.innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>名称</th>
              <th>图标</th>
              <th>账号信息</th>
              <th>排序</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${configs.map(c => `
              <tr>
                <td>${esc(c.id)}</td>
                <td>${esc(c.name)}</td>
                <td>${esc(c.icon || '-')}</td>
                <td>${esc(c.account_info?.substring(0, 30) || '-')}...</td>
                <td>${esc(c.sort_order?.toString() || '0')}</td>
                <td>${c.active ? '<span class="badge success">启用</span>' : '<span class="badge">禁用</span>'}</td>
                <td>
                  <button class="btn small" data-action="edit-payment" data-id="${esc(c.id)}" data-name="${esc(c.name)}" data-icon="${esc(c.icon || '')}" data-sort="${esc(c.sort_order || 0)}" data-active="${c.active ? 'true' : 'false'}">编辑</button>
                  <button class="btn small danger" data-action="delete-payment" data-id="${esc(c.id)}">删除</button>
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

  async function savePaymentConfig() {
    let configId = qs('#paymentConfigId').value ? Number(qs('#paymentConfigId').value) : null;
    const payload = {
      name: (qs('#paymentName').value || '').trim(),
      icon: qs('#paymentIcon').value,
      account_info: qs('#paymentAccountInfo').value,
      instructions: (qs('#paymentInstructions').value || '').trim() || null,
      sort_order: Number(qs('#paymentSort').value || '0'),
      active: qs('#paymentActive').value === 'true',
    };

    if (configId && !state.paymentConfigsById[String(configId)]) {
      configId = null;
      qs('#paymentConfigId').value = '';
    }

    const method = configId ? 'PATCH' : 'POST';
    const url = configId ? `/payment-configs/${configId}` : '/payment-configs';

    try {
      await apiRequest(url, { method, body: payload });
      toast({ title: '保存成功', message: '', type: 'success' });
      clearPaymentForm();
      await loadPaymentConfigs();
    } catch (e) {
      toast({ title: '保存失败', message: formatError(e), type: 'error' });
    }
  }

  function fillPaymentForm(config) {
    if (!config) return;

    qs('#paymentConfigId').value = config.id || '';
    qs('#paymentName').value = config.name || '';
    qs('#paymentIcon').value = config.icon || '';
    qs('#paymentAccountInfo').value = config.account_info || '';
    qs('#paymentInstructions').value = config.instructions || '';
    qs('#paymentSort').value = String(config.sort_order || 0);
    qs('#paymentActive').value = config.active ? 'true' : 'false';

    const fileEl = qs('#paymentQrFile');
    if (fileEl) fileEl.value = '';
    if (paymentQrObjectUrl) {
      URL.revokeObjectURL(paymentQrObjectUrl);
      paymentQrObjectUrl = null;
    }
    setPaymentQrPreview(extractFirstImgSrc(qs('#paymentAccountInfo').value));
  }

  function clearPaymentForm() {
    qs('#paymentConfigId').value = '';
    qs('#paymentName').value = '';
    qs('#paymentAccountInfo').value = '';
    qs('#paymentInstructions').value = '';
    qs('#paymentSort').value = '0';
    qs('#paymentActive').value = 'true';

    const fileEl = qs('#paymentQrFile');
    if (fileEl) fileEl.value = '';
    if (paymentQrObjectUrl) {
      URL.revokeObjectURL(paymentQrObjectUrl);
      paymentQrObjectUrl = null;
    }
    setPaymentQrPreview('');
  }

  async function deletePaymentConfig(id) {
    if (!confirm('确定要删除这个支付配置吗？')) return;

    try {
      await apiRequest(`/payment-configs/${id}`, { method: 'DELETE' });
      const currentId = qs('#paymentConfigId').value ? Number(qs('#paymentConfigId').value) : null;
      if (currentId === id) clearPaymentForm();
      toast({ title: '删除成功', message: '', type: 'success' });
      await loadPaymentConfigs();
    } catch (e) {
      toast({ title: '删除失败', message: formatError(e), type: 'error' });
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

  // === 审核操作 ===
  function openRechargeRejectModal(id) {
    state.reviewRequest = { kind: 'recharge', id };

    const overlay = qs('#reviewModal');
    if (!overlay) return;

    const titleEl = overlay.querySelector('.title');
    if (titleEl) titleEl.textContent = '拒绝充值申请';

    const contentEl = qs('#reviewContent');
    if (contentEl) {
      contentEl.innerHTML = `
        <div class="field">
          <label>拒绝原因（会展示给用户）</label>
          <textarea class="input" id="reviewNoteInput" rows="4" placeholder="请输入拒绝原因"></textarea>
          <div class="hint" style="margin-top: 8px;">默认已填，可直接修改</div>
        </div>
      `;
      const noteInput = qs('#reviewNoteInput');
      if (noteInput) noteInput.value = DEFAULT_RECHARGE_REJECT_NOTE;
    }

    const cancelBtn = qs('#cancelReviewBtn');
    const rejectBtn = qs('#rejectReviewBtn');
    const approveBtn = qs('#approveReviewBtn');

    if (cancelBtn) cancelBtn.textContent = '取消';
    if (rejectBtn) {
      rejectBtn.textContent = '确认拒绝';
      rejectBtn.classList.remove('hidden');
      rejectBtn.disabled = false;
      rejectBtn.classList.remove('disabled');
    }
    if (approveBtn) approveBtn.classList.add('hidden');

    overlay.classList.remove('hidden');

    setTimeout(() => {
      const noteInput = qs('#reviewNoteInput');
      if (!noteInput) return;
      noteInput.focus();
      noteInput.select();
    }, 0);
  }

  function closeReviewModal() {
    const overlay = qs('#reviewModal');
    if (!overlay) return;
    overlay.classList.add('hidden');

    const titleEl = overlay.querySelector('.title');
    if (titleEl) titleEl.textContent = '审核确认';

    const contentEl = qs('#reviewContent');
    if (contentEl) contentEl.innerHTML = '';

    const rejectBtn = qs('#rejectReviewBtn');
    if (rejectBtn) {
      rejectBtn.textContent = '拒绝';
      rejectBtn.disabled = false;
      rejectBtn.classList.remove('disabled');
    }
    const approveBtn = qs('#approveReviewBtn');
    if (approveBtn) approveBtn.classList.remove('hidden');

    state.reviewRequest = null;
  }

  async function reviewRecharge(id, action, note = null) {
    try {
      await apiRequest(`/admin/recharge-requests/${id}/${action}`, { method: 'POST', body: { note } });
      toast({ title: '操作成功', message: `充值 #${id} ${action}`, type: 'success' });
      await loadRecharges(state.currentFilter);
      await loadDashboard();
    } catch (e) {
      toast({ title: '操作失败', message: formatError(e), type: 'error' });
    }
  }

  async function reviewRefund(id, action) {
    try {
      await apiRequest(`/admin/refund-requests/${id}/${action}`, { method: 'POST', body: { note: null } });
      toast({ title: '操作成功', message: `退款 #${id} ${action}`, type: 'success' });
      await loadRefunds(state.currentFilter);
      await loadDashboard();
    } catch (e) {
      toast({ title: '操作失败', message: formatError(e), type: 'error' });
    }
  }

  // === 事件绑定 ===
  function bindEvents() {
    // 导航
    qsa('.nav-item').forEach(item => {
      item.addEventListener('click', () => setPage(item.dataset.page));
    });

    // 菜单切换（移动端）
    qs('#menuToggle').addEventListener('click', () => {
      qs('#sidebar').classList.toggle('open');
    });

    // 数据概览刷新
    qs('#refreshDashboard').addEventListener('click', () => loadDashboard());

    // 审核弹窗
    const cancelReviewBtn = qs('#cancelReviewBtn');
    if (cancelReviewBtn) cancelReviewBtn.addEventListener('click', closeReviewModal);

    const rejectReviewBtn = qs('#rejectReviewBtn');
    if (rejectReviewBtn) {
      rejectReviewBtn.addEventListener('click', async () => {
        const req = state.reviewRequest;
        if (!req || req.kind !== 'recharge') {
          closeReviewModal();
          return;
        }

        const note = (qs('#reviewNoteInput')?.value || '').trim();
        if (!note) {
          toast({ title: '请输入拒绝原因', message: '', type: 'error' });
          return;
        }

        const oldText = rejectReviewBtn.textContent;
        rejectReviewBtn.disabled = true;
        rejectReviewBtn.textContent = '提交中...';
        rejectReviewBtn.classList.add('disabled');

        try {
          await reviewRecharge(req.id, 'reject', note);
          closeReviewModal();
        } finally {
          rejectReviewBtn.disabled = false;
          rejectReviewBtn.textContent = oldText || '确认拒绝';
          rejectReviewBtn.classList.remove('disabled');
        }
      });
    }

    // 充值审核
    qs('#loadRechargesBtn').addEventListener('click', () => loadRecharges(state.currentFilter));
    qsa('#page-recharges .filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        qsa('#page-recharges .filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentFilter = btn.dataset.status;
        loadRecharges(state.currentFilter);
      });
    });
    const rechargeList = qs('#rechargeList');
    if (rechargeList) {
      rechargeList.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action="review-recharge"]');
        if (!btn) return;
        const id = Number(btn.dataset.id || '0');
        const action = btn.dataset.review;
        if (!id) return;
        if (action !== 'approve' && action !== 'reject') return;
        if (action === 'reject') {
          openRechargeRejectModal(id);
          return;
        }
        reviewRecharge(id, action);
      });
    }

    // 退款审核
    qs('#loadRefundsBtn').addEventListener('click', () => loadRefunds(state.currentFilter));
    qsa('#page-refunds .filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        qsa('#page-refunds .filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentFilter = btn.dataset.status;
        loadRefunds(state.currentFilter);
      });
    });
    const refundList = qs('#refundList');
    if (refundList) {
      refundList.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action="review-refund"]');
        if (!btn) return;
        const id = Number(btn.dataset.id || '0');
        const action = btn.dataset.review;
        if (!id) return;
        if (action !== 'approve' && action !== 'reject') return;
        reviewRefund(id, action);
      });
    }

    // 产品管理
    qs('#loadProductsBtn').addEventListener('click', () => loadProducts());
    qs('#updateProductBtn').addEventListener('click', updateProduct);
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
          btn.dataset.active === 'true',
        );
      });
    }

    // 卡密管理
    qs('#importCardsBtn').addEventListener('click', importCards);
    qs('#inventoryBtn').addEventListener('click', checkInventory);
    qs('#loadCardsBtn').addEventListener('click', loadCards);

    // 订单记录
    qs('#loadOrdersBtn').addEventListener('click', () => loadOrders(state.currentPeriod));
    qsa('#page-orders .filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        qsa('#page-orders .filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentPeriod = btn.dataset.period;
        loadOrders(state.currentPeriod);
      });
    });

    // 用户管理
    qs('#loadUsersBtn').addEventListener('click', () => loadUsers());

    // API Key
    qs('#loadApiKeysBtn').addEventListener('click', () => loadApiKeys());
    qs('#createApiKeyBtn').addEventListener('click', createApiKey);

    // 支付配置
    qs('#loadPaymentsBtn').addEventListener('click', () => loadPaymentConfigs());
    qs('#savePaymentBtn').addEventListener('click', savePaymentConfig);
    qs('#clearPaymentBtn').addEventListener('click', clearPaymentForm);
    const paymentsList = qs('#paymentsList');
    if (paymentsList) {
      paymentsList.addEventListener('click', (e) => {
        const editBtn = e.target.closest('button[data-action="edit-payment"]');
        if (editBtn) {
          const id = Number(editBtn.dataset.id || '0');
          if (!id) return;
          const config = state.paymentConfigsById[String(id)];
          if (!config) {
            toast({ title: '配置不存在', message: '该支付配置可能已被删除，请刷新列表后重试', type: 'error' });
            clearPaymentForm();
            loadPaymentConfigs();
            return;
          }
          fillPaymentForm(config);
          return;
        }

        const delBtn = e.target.closest('button[data-action="delete-payment"]');
        if (delBtn) {
          const id = Number(delBtn.dataset.id || '0');
          if (!id) return;
          deletePaymentConfig(id);
        }
      });
    }

    const uploadBtn = qs('#uploadPaymentQrBtn');
    if (uploadBtn) uploadBtn.addEventListener('click', uploadPaymentQr);

    const qrFileEl = qs('#paymentQrFile');
    if (qrFileEl) {
      qrFileEl.addEventListener('change', () => {
        if (paymentQrObjectUrl) {
          URL.revokeObjectURL(paymentQrObjectUrl);
          paymentQrObjectUrl = null;
        }
        const f = qrFileEl.files && qrFileEl.files[0];
        if (!f) {
          setPaymentQrPreview('');
          return;
        }
        paymentQrObjectUrl = URL.createObjectURL(f);
        setPaymentQrPreview(paymentQrObjectUrl);
      });
    }

    const accountInfoEl = qs('#paymentAccountInfo');
    if (accountInfoEl) {
      accountInfoEl.addEventListener('input', () => {
        if (paymentQrObjectUrl) return;
        setPaymentQrPreview(extractFirstImgSrc(accountInfoEl.value));
      });
    }

    // 公告配置
    const loadAnnouncementBtn = qs('#loadAnnouncementBtn');
    if (loadAnnouncementBtn) loadAnnouncementBtn.addEventListener('click', () => loadAnnouncementConfig());
    const saveAnnouncementBtn = qs('#saveAnnouncementBtn');
    if (saveAnnouncementBtn) saveAnnouncementBtn.addEventListener('click', saveAnnouncementConfig);
    const uploadAnnouncementBtn = qs('#uploadAnnouncementQrBtn');
    if (uploadAnnouncementBtn) uploadAnnouncementBtn.addEventListener('click', uploadAnnouncementQr);

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

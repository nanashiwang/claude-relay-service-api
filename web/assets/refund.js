(function () {
  const { qs, apiRequest, requireAuth, toast, formatError, moneyFromCents, escapeHtml: esc } = window.App;

  const state = {
    wallet: null
  };

  // 加载钱包信息
  async function loadWallet() {
    try {
      state.wallet = await apiRequest('/wallet');
      updateBalanceDisplay();
    } catch (e) {
      console.error('Failed to load wallet', e);
    }
  }

  // 更新余额显示
  function updateBalanceDisplay() {
    if (!state.wallet) return;
    const balance = moneyFromCents(state.wallet.balance_cents, state.wallet.currency);
    qs('#balanceText').textContent = balance;
    qs('#availableBalance').textContent = balance;
    qs('#currentBalance').textContent = balance;
    updateRefundPreview();
  }

  // 更新退款预览
  function updateRefundPreview() {
    const amountInput = qs('#refundAmount');
    const amountValue = parseFloat(amountInput.value);
    const amountCents = Number.isFinite(amountValue) ? Math.round(Math.max(0, amountValue) * 100) : 0;
    const currency = qs('#refundCurrency').value;

    const currentCents = state.wallet?.balance_cents || 0;
    const currentCurrency = state.wallet?.currency || 'CNY';

    const amountDisplay = moneyFromCents(amountCents, currency);
    const afterCents = currentCents - amountCents;
    const afterDisplay = moneyFromCents(Math.max(0, afterCents), currentCurrency);

    qs('#refundAmountDisplay').textContent = `-${amountDisplay}`;
    qs('#afterBalance').textContent = afterDisplay;

    // 余额不足时警告
    if (amountCents > currentCents) {
      qs('#afterBalance').style.color = 'var(--danger)';
      qs('#afterBalance').textContent = `${afterDisplay} (余额不足)`;
    } else {
      qs('#afterBalance').style.color = 'var(--text)';
    }
  }

  // 提交退款申请
  async function submitRefund() {
    const amountValue = parseFloat(qs('#refundAmount').value);
    const amountCents = Number.isFinite(amountValue) ? Math.round(Math.max(0, amountValue) * 100) : 0;
    const currency = qs('#refundCurrency').value;
    const reason = qs('#refundReason').value.trim();

    if (amountCents <= 0) {
      toast({ title: '金额错误', message: '请输入有效的退款金额', type: 'error' });
      return;
    }

    if (!reason) {
      toast({ title: '缺少原因', message: '请填写退款原因', type: 'error' });
      return;
    }

    const currentCents = state.wallet?.balance_cents || 0;
    if (amountCents > currentCents) {
      toast({ title: '余额不足', message: '退款金额不能超过当前余额', type: 'error' });
      return;
    }

    const btn = qs('#submitRefundBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '提交中...';

    try {
      const payload = {
        amount_cents: amountCents,
        currency,
        reason
      };

      await apiRequest('/refund-requests', { method: 'POST', body: payload });

      // 显示成功弹窗
      qs('#successModal').classList.remove('hidden');

      // 重置表单
      qs('#refundAmount').value = '';
      qs('#refundReason').value = '';
      updateRefundPreview();

      // 刷新历史
      loadRefundHistory();

    } catch (e) {
      toast({ title: '提交失败', message: formatError(e), type: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }

  // 加载退款历史
  async function loadRefundHistory() {
    try {
      const requests = await apiRequest('/refund-requests');

      if (requests.length === 0) {
        qs('#refundList').innerHTML = '<div class="muted-2" style="text-align: center; padding: 20px;">暂无退款记录</div>';
        return;
      }

      const statusMap = {
        'pending': '<span class="badge warn">pending</span>',
        'approved': '<span class="badge success">approved</span>',
        'rejected': '<span class="badge danger">rejected</span>',
        'canceled': '<span class="badge">canceled</span>'
      };

      qs('#refundList').innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>时间</th>
              <th>金额</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            ${requests.map(r => `
              <tr>
                <td>${esc(r.created_at || '')}</td>
                <td>${moneyFromCents(r.amount_cents, r.currency)}</td>
                <td>${statusMap[r.status] || r.status}</td>
              </tr>
              ${r.reason ? `<tr><td colspan="3" class="muted-2" style="font-size: 11px;">原因：${esc(r.reason)}</td></tr>` : ''}
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      console.error('Failed to load refund history', e);
    }
  }

  // 初始化
  qs('#refundAmount').addEventListener('input', updateRefundPreview);
  qs('#refundCurrency').addEventListener('change', updateRefundPreview);
  qs('#submitRefundBtn').addEventListener('click', submitRefund);
  qs('#refreshHistoryBtn').addEventListener('click', () => {
    loadRefundHistory();
    toast({ title: '已刷新', message: '退款记录已更新', type: 'success' });
  });
  qs('#closeSuccessBtn').addEventListener('click', () => {
    qs('#successModal').classList.add('hidden');
  });

  // 初始加载
  (async () => {
    await requireAuth();
    await loadWallet();
    await loadRefundHistory();
  })().catch(e => {
    toast({ title: '初始化失败', message: formatError(e), type: 'error' });
  });
})();

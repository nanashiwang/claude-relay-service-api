(function () {
  const { qs, qsa, apiRequest, requireAuth, toast, formatError, moneyFromCents, escapeHtml: esc } = window.App;

  const state = {
    wallet: null,
    amountCents: 20000,
    selectedPayment: null,
    paymentConfigs: [],
    paymentProofUrl: null
  };

  const paymentProofFile = qs('#paymentProofFile');
  const uploadPaymentProofBtn = qs('#uploadPaymentProofBtn');
  const paymentProofPreview = qs('#paymentProofPreview');
  const paymentProofPreviewEmpty = qs('#paymentProofPreviewEmpty');

  // 加载钱包信息
  async function loadWallet() {
    try {
      state.wallet = await apiRequest('/wallet');
      qs('#balanceText').textContent = moneyFromCents(state.wallet.balance_cents, state.wallet.currency);
    } catch (e) {
      qs('#balanceText').textContent = '加载失败';
    }
  }

  // 加载支付配置
  async function loadPaymentConfigs() {
    try {
      state.paymentConfigs = await apiRequest('/payment-configs?active_only=true');
      renderPaymentMethods();
    } catch (e) {
      // 如果接口不存在或出错，显示默认支付方式
      state.paymentConfigs = [
        {
          id: 1,
          name: '支付宝',
          icon: 'alipay',
          account_info: '请使用支付宝扫码支付',
          instructions: '转账时请备注您的用户名'
        },
        {
          id: 2,
          name: '微信',
          icon: 'wechat',
          account_info: '请使用微信扫码支付',
          instructions: '转账时请备注您的用户名'
        },
        {
          id: 3,
          name: '银行卡',
          icon: 'bank',
          account_info: '户名：XXX<br>银行：中国银行<br>账号：6217 XXXX XXXX XXXX',
          instructions: '转账后请保存好凭证'
        }
      ];
      renderPaymentMethods();
    }
  }

  // 渲染支付方式
  function renderPaymentMethods() {
    const container = qs('#paymentMethods');

    if (state.paymentConfigs.length === 0) {
      container.innerHTML = '<div class="muted-2">暂无可用支付方式，请联系管理员配置</div>';
      return;
    }

    container.innerHTML = state.paymentConfigs.map(config => {
      let iconSvg = '';
      if (config.icon === 'alipay') {
        iconSvg = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15H9V7h2v10zm4 0h-2V7h2v10z" fill="currentColor"/></svg>';
      } else if (config.icon === 'wechat') {
        iconSvg = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor"/></svg>';
      } else {
        iconSvg = '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M7 15h2M11 15h4" stroke="currentColor" stroke-width="2"/></svg>';
      }

      return `
        <div class="payment-card" data-id="${config.id}">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div class="icon" style="display: flex; align-items: center; justify-content: center; background: var(--surface); border-radius: 8px; padding: 8px;">
              ${iconSvg}
            </div>
            <div>
              <div class="name">${esc(config.name)}</div>
              <div class="account-info">${config.instructions ? esc(config.instructions) : '点击查看收款信息'}</div>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // 绑定点击事件
    qsa('.payment-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = parseInt(card.dataset.id, 10);
        selectPayment(id);
      });
    });
  }

  // 选择支付方式
  function selectPayment(id) {
    state.selectedPayment = state.paymentConfigs.find(c => c.id === id);

    qsa('.payment-card').forEach(card => {
      card.classList.toggle('selected', parseInt(card.dataset.id, 10) === id);
    });

    // 显示支付信息
    const infoPanel = qs('#paymentInfo');
    const accountInfo = qs('#paymentAccountInfo');

    if (state.selectedPayment) {
      infoPanel.style.display = 'block';
      accountInfo.innerHTML = `
        <div style="font-size: 14px; line-height: 1.8;">
          <strong>${esc(state.selectedPayment.name)}</strong><br>
          ${state.selectedPayment.account_info}
        </div>
        ${state.selectedPayment.instructions ? `<div class="hint" style="margin-top: 8px;">${esc(state.selectedPayment.instructions)}</div>` : ''}
      `;
    } else {
      infoPanel.style.display = 'none';
    }
  }

  function setPaymentProofPreview(url) {
    if (!paymentProofPreview || !paymentProofPreviewEmpty) return;
    if (url) {
      paymentProofPreview.src = url;
      paymentProofPreview.style.display = 'block';
      paymentProofPreviewEmpty.style.display = 'none';
    } else {
      paymentProofPreview.removeAttribute('src');
      paymentProofPreview.style.display = 'none';
      paymentProofPreviewEmpty.style.display = 'block';
    }
  }

  async function uploadPaymentProof() {
    if (!paymentProofFile || !uploadPaymentProofBtn) return;
    const file = paymentProofFile.files && paymentProofFile.files[0];
    if (!file) {
      toast({ title: '请选择截图', message: '请先选择要上传的截图', type: 'error' });
      return;
    }

    uploadPaymentProofBtn.disabled = true;
    const originalText = uploadPaymentProofBtn.textContent;
    uploadPaymentProofBtn.textContent = '上传中...';

    try {
      const form = new FormData();
      form.append('file', file);
      const data = await apiRequest('/recharge-requests/upload-proof', { method: 'POST', body: form });
      state.paymentProofUrl = data?.url || null;
      setPaymentProofPreview(state.paymentProofUrl);
      toast({ title: '上传成功', message: '', type: 'success' });
    } catch (e) {
      toast({ title: '上传失败', message: formatError(e), type: 'error' });
    } finally {
      uploadPaymentProofBtn.disabled = false;
      uploadPaymentProofBtn.textContent = originalText;
    }
  }

  // 更新金额显示
  function updateAmountDisplay() {
    qs('#confirmAmount').textContent = `¥${(state.amountCents / 100).toFixed(2)}`;
  }

  // 快捷金额选择
  qsa('.amount-option').forEach(btn => {
    btn.addEventListener('click', () => {
      qsa('.amount-option').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.amountCents = parseInt(btn.dataset.amount, 10);
      qs('#customAmount').value = '';
      updateAmountDisplay();
    });
  });

  // 自定义金额
  qs('#customAmount').addEventListener('input', (e) => {
    const value = parseFloat(e.target.value) || 0;
    if (value > 0) {
      state.amountCents = Math.round(value * 100);
      qsa('.amount-option').forEach(b => b.classList.remove('active'));
      updateAmountDisplay();
    }
  });

  // 提交充值申请
  async function submitRecharge() {
    if (state.amountCents <= 0) {
      toast({ title: '金额错误', message: '请选择或输入充值金额', type: 'error' });
      return;
    }

    if (!state.selectedPayment) {
      toast({ title: '未选择支付方式', message: '请选择支付方式', type: 'error' });
      return;
    }

    const btn = qs('#submitRechargeBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '提交中...';

    try {
      const payload = {
        amount_cents: state.amountCents,
        currency: 'CNY',
        payment_method: state.selectedPayment.name,
        payment_reference: qs('#paymentRef').value.trim() || null,
        payment_proof_url: state.paymentProofUrl || null,
        note: qs('#rechargeNote').value.trim() || null
      };

      await apiRequest('/recharge-requests', { method: 'POST', body: payload });

      // 显示成功弹窗
      qs('#successModal').classList.remove('hidden');

      // 重置表单
      qs('#paymentRef').value = '';
      qs('#rechargeNote').value = '';
      if (paymentProofFile) paymentProofFile.value = '';
      state.paymentProofUrl = null;
      setPaymentProofPreview(null);
      state.amountCents = 20000;
      updateAmountDisplay();

      // 刷新历史
      loadRechargeHistory();

    } catch (e) {
      toast({ title: '提交失败', message: formatError(e), type: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }

  // 加载充值历史
  async function loadRechargeHistory() {
    try {
      const requests = await apiRequest('/recharge-requests');

      if (requests.length === 0) {
        qs('#rechargeList').innerHTML = '<div class="muted-2" style="text-align: center; padding: 20px;">暂无充值记录</div>';
        return;
      }

      const statusMap = {
        'pending': '<span class="badge warn">pending</span>',
        'approved': '<span class="badge success">approved</span>',
        'rejected': '<span class="badge danger">rejected</span>',
        'canceled': '<span class="badge">canceled</span>'
      };

      qs('#rechargeList').innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>时间</th>
              <th>金额</th>
              <th>支付方式</th>
              <th>凭证</th>
              <th>审核备注</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            ${requests.map(r => {
              const reviewNote = (r.review_note || '').trim();
              const shortNote = reviewNote ? (reviewNote.length > 20 ? reviewNote.slice(0, 20) + '...' : reviewNote) : '-';
              const proofUrl = r.payment_proof_url ? esc(r.payment_proof_url) : '';
              return `
                <tr>
                  <td>${esc(r.created_at || '')}</td>
                  <td>${moneyFromCents(r.amount_cents, r.currency)}</td>
                  <td>${esc(r.payment_method || '-')}</td>
                  <td>${proofUrl ? `<a href="${proofUrl}" target="_blank" rel="noreferrer">查看</a>` : '-'}</td>
                  <td title="${esc(reviewNote)}">${esc(shortNote)}</td>
                  <td>${statusMap[r.status] || r.status}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      console.error('Failed to load recharge history', e);
    }
  }

  // 初始化
  qs('#submitRechargeBtn').addEventListener('click', submitRecharge);
  if (uploadPaymentProofBtn) uploadPaymentProofBtn.addEventListener('click', uploadPaymentProof);
  qs('#refreshHistoryBtn').addEventListener('click', () => {
    loadRechargeHistory();
    toast({ title: '已刷新', message: '充值记录已更新', type: 'success' });
  });
  qs('#closeSuccessBtn').addEventListener('click', () => {
    qs('#successModal').classList.add('hidden');
  });

  // 初始加载
  (async () => {
    await requireAuth();
    await loadWallet();
    await loadPaymentConfigs();
    await loadRechargeHistory();
    updateAmountDisplay();
  })().catch(e => {
    toast({ title: '初始化失败', message: formatError(e), type: 'error' });
  });
})();

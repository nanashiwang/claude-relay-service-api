(function () {
  const {
    qs,
    qsa,
    apiRequest,
    requireAuth,
    clearToken,
    toast,
    formatError,
    moneyFromCents,
    pretty,
    escapeHtml: esc,
    prefetchShopCache,
  } = window.App;

  const state = {
    me: null,
    wallet: null,
  };

  const announcementModal = qs("#announcementModal");
  const announcementTitle = qs("#announcementTitle");
  const announcementContent = qs("#announcementContent");
  const announcementQrImg = qs("#announcementQrImg");
  const announcementQrEmpty = qs("#announcementQrEmpty");
  const announcementCloseBtn = qs("#announcementCloseBtn");

  const referralCodeEl = qs("#referralCode");
  const referralTotalEl = qs("#referralTotal");
  const referralCountEl = qs("#referralCount");
  const referralLinkEl = qs("#referralLink");
  const referrerNameEl = qs("#referrerName");
  const bindReferrerWrap = qs("#bindReferrerWrap");
  const referrerCodeInput = qs("#referrerCodeInput");
  const referralRebateList = qs("#referralRebateList");
  const refreshReferralBtn = qs("#refreshReferralBtn");
  const copyReferralBtn = qs("#copyReferralBtn");
  const copyReferralLinkBtn = qs("#copyReferralLinkBtn");
  const bindReferrerBtn = qs("#bindReferrerBtn");

  const navButtons = qsa("[data-nav]");
  const viewEls = qsa("[data-view]");

  function setView(name) {
    navButtons.forEach((b) => b.classList.toggle("active", b.dataset.nav === name));
    viewEls.forEach((v) => v.classList.toggle("hidden", v.dataset.view !== name));
    localStorage.setItem("dashboard_view", name);
  }

  function gotoLogin() {
    window.location.href = "/";
  }

  function renderMarkdown(text) {
    const safe = esc(String(text || "")).replace(/\r\n?/g, "\n");
    const lines = safe.split("\n");
    const out = [];
    let inUl = false;
    let inOl = false;

    const closeLists = () => {
      if (inUl) {
        out.push("</ul>");
        inUl = false;
      }
      if (inOl) {
        out.push("</ol>");
        inOl = false;
      }
    };

    const inline = (input) => {
      let value = input;
      value = value.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
      value = value.replace(/\[(.+?)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
      value = value.replace(/(https?:\/\/[^\s<]+[^<.,:;"')\]\s])/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>');
      return value;
    };

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) {
        closeLists();
        out.push("<p></p>");
        return;
      }
      if (/^#{1,3}\s+/.test(trimmed)) {
        closeLists();
        const level = Math.min(3, trimmed.match(/^#{1,3}/)[0].length);
        const content = trimmed.replace(/^#{1,3}\s+/, "");
        out.push(`<h${level}>${inline(content)}</h${level}>`);
        return;
      }
      if (/^[-*]\s+/.test(trimmed)) {
        if (inOl) {
          out.push("</ol>");
          inOl = false;
        }
        if (!inUl) {
          out.push("<ul>");
          inUl = true;
        }
        out.push(`<li>${inline(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
        return;
      }
      if (/^\d+\.\s+/.test(trimmed)) {
        if (inUl) {
          out.push("</ul>");
          inUl = false;
        }
        if (!inOl) {
          out.push("<ol>");
          inOl = true;
        }
        out.push(`<li>${inline(trimmed.replace(/^\d+\.\s+/, ""))}</li>`);
        return;
      }
      if (/^(-{3,}|_{3,}|一{6,}|={3,})$/.test(trimmed)) {
        closeLists();
        out.push("<hr />");
        return;
      }
      closeLists();
      out.push(`<p>${inline(trimmed)}</p>`);
    });
    closeLists();
    return out.join("");
  }

  function closeAnnouncement() {
    if (announcementModal) announcementModal.classList.add("hidden");
  }

  async function loadAnnouncement() {
    if (!announcementModal) return;
    try {
      const data = await apiRequest("/announcement");
      if (!data || data.active === false) return;

      if (announcementTitle) announcementTitle.textContent = data.title || "平台公告";
      if (announcementContent) announcementContent.innerHTML = renderMarkdown(data.content || "");

      const qrUrl = data.group_qr_url || "";
      if (announcementQrImg) {
        if (qrUrl) {
          announcementQrImg.src = qrUrl;
          announcementQrImg.style.display = "block";
          if (announcementQrEmpty) announcementQrEmpty.style.display = "none";
        } else {
          announcementQrImg.removeAttribute("src");
          announcementQrImg.style.display = "none";
          if (announcementQrEmpty) announcementQrEmpty.style.display = "block";
        }
      }

      announcementModal.classList.remove("hidden");
    } catch (e) {
      console.warn("Failed to load announcement", e);
    }
  }

  async function loadMe() {
    state.me = await requireAuth();
    qs("#userText").textContent = state.me.username;
    qs("#adminTag").classList.toggle("hidden", !state.me.is_admin);

    const adminEntryCard = qs("#adminEntryCard");
    if (adminEntryCard) adminEntryCard.classList.toggle("hidden", !state.me.is_admin);

    return state.me;
  }

  async function loadWallet() {
    try {
      state.wallet = await apiRequest("/wallet");
      const balance = moneyFromCents(state.wallet.balance_cents, state.wallet.currency);

      // 更新所有余额显示
      if (qs("#balanceText")) qs("#balanceText").textContent = balance;
      if (qs("#balanceTopText")) qs("#balanceTopText").textContent = balance;
      if (qs("#statBalance")) qs("#statBalance").textContent = balance;
      if (qs("#walletJson")) qs("#walletJson").textContent = pretty(state.wallet);

      // 计算统计数据
      await updateStats();
    } catch (e) {
      console.error("Failed to load wallet", e);
    }
  }

  async function updateStats() {
    try {
      const txs = await apiRequest("/wallet/transactions?limit=100");

      // 计算本月消费
      const now = new Date();
      const thisMonth = now.getMonth();
      const thisYear = now.getFullYear();

      let monthlySpent = 0;
      let totalPurchased = 0;

      txs.forEach(t => {
        const txDate = new Date(t.created_at || "");
        if (t.kind === "purchase") {
          totalPurchased++;
          if (txDate.getMonth() === thisMonth && txDate.getFullYear() === thisYear) {
            monthlySpent += Math.abs(t.amount_cents);
          }
        }
      });

      const currency = state.wallet?.currency || "CNY";
      if (qs("#statSpent")) qs("#statSpent").textContent = moneyFromCents(monthlySpent, currency);
      if (qs("#statPurchased")) qs("#statPurchased").textContent = totalPurchased;

      // 渲染最近交易
      renderRecentTx(txs.slice(0, 5));

    } catch (e) {
      console.error("Failed to update stats", e);
    }
  }

  function txKindLabel(tx) {
    if (tx && tx.reference_type === "referral_rebate") return "返利";
    const kind = String(tx?.kind || "");
    if (kind === "recharge") return "充值";
    if (kind === "purchase") return "购买";
    if (kind === "refund") return "退款";
    if (kind === "adjustment") return "调整";
    return kind || "-";
  }

  function renderRecentTx(txs) {
    const wrap = qs("#recentTxList");
    if (!wrap) return;

    if (!txs || txs.length === 0) {
      wrap.innerHTML = '<div class="muted-2">暂无交易记录</div>';
      return;
    }

    wrap.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>类型</th>
            <th>金额</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          ${txs.map(t => `
            <tr>
              <td>${esc(txKindLabel(t))}</td>
              <td style="color: ${t.amount_cents >= 0 ? 'var(--success)' : 'var(--danger)'};">
                ${t.amount_cents >= 0 ? '+' : ''}${moneyFromCents(t.amount_cents, t.currency)}
              </td>
              <td>${esc(t.created_at || "")}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  async function loadWalletTx() {
    try {
      const rows = await apiRequest("/wallet/transactions");

      if (qs("#txJson")) qs("#txJson").textContent = pretty(rows);

      const wrap = qs("#txTableWrap");
      if (!wrap) return;

      if (!rows || rows.length === 0) {
        wrap.innerHTML = '<div class="muted">暂无流水</div>';
        return;
      }

      const head = `
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>类型</th>
              <th>金额</th>
              <th>余额</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
      `;
      const body = rows
        .map((r) => {
          const amount = moneyFromCents(r.amount_cents, r.currency);
          const after = moneyFromCents(r.balance_after_cents, r.currency);
          return `
            <tr>
              <td>${esc(r.id)}</td>
              <td>${esc(txKindLabel(r))}</td>
              <td style="color: ${r.amount_cents >= 0 ? 'var(--success)' : 'var(--danger)'};">${esc(amount)}</td>
              <td>${esc(after)}</td>
              <td>${esc(r.created_at || "")}</td>
            </tr>
          `;
        })
        .join("");
      const tail = "</tbody></table>";
      wrap.innerHTML = head + body + tail;
    } catch (e) {
      console.error("Failed to load transactions", e);
    }
  }

  function buildReferralLink(code) {
    return `${location.origin}/?ref=${encodeURIComponent(code)}`;
  }

  async function copyText(text) {
    const value = String(text || "");
    if (!value) return false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
        return true;
      }
    } catch {}

    const ta = document.createElement("textarea");
    ta.value = value;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }

  function renderReferralSummary(data) {
    if (!data) return;
    if (referralCodeEl) referralCodeEl.textContent = data.referral_code || "-";
    if (referralTotalEl) referralTotalEl.textContent = moneyFromCents(data.total_rebate_cents || 0, data.currency || "CNY");
    if (referralCountEl) referralCountEl.textContent = data.referred_count ?? 0;
    if (referralLinkEl) referralLinkEl.textContent = data.referral_code ? buildReferralLink(data.referral_code) : "-";

    const referrerName = data.referrer_username || "";
    if (referrerNameEl) referrerNameEl.textContent = referrerName || "未绑定";
    if (bindReferrerWrap) bindReferrerWrap.classList.toggle("hidden", !!referrerName);
  }

  function renderReferralRebates(rows) {
    if (!referralRebateList) return;
    if (!rows || rows.length === 0) {
      referralRebateList.innerHTML = '<div class="muted-2">暂无返利记录</div>';
      return;
    }

    referralRebateList.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>来源用户</th>
            <th>金额</th>
            <th>购卡ID</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr>
              <td>${esc(r.id)}</td>
              <td>${esc(r.referred_username || r.referred_user_id)}</td>
              <td style="color: var(--success);">+${moneyFromCents(r.amount_cents, r.currency)}</td>
              <td>${esc(r.card_claim_id)}</td>
              <td>${esc(r.created_at || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  async function loadReferralSummary() {
    const data = await apiRequest("/referrals/me");
    renderReferralSummary(data);
    return data;
  }

  async function loadReferralRebates() {
    const rows = await apiRequest("/referrals/rebates?limit=50");
    renderReferralRebates(rows);
    return rows;
  }

  async function refreshReferral() {
    try {
      await loadReferralSummary();
      await loadReferralRebates();
      toast({ title: "已刷新", message: "", type: "success" });
    } catch (e) {
      toast({ title: "加载失败", message: formatError(e), type: "error" });
    }
  }

  async function bindReferrer() {
    if (!referrerCodeInput) return;
    const code = (referrerCodeInput.value || "").trim();
    if (!code) {
      toast({ title: "请输入推广码", message: "", type: "error" });
      return;
    }
    if (bindReferrerBtn) bindReferrerBtn.disabled = true;
    try {
      const data = await apiRequest("/referrals/bind", { method: "POST", body: { code } });
      renderReferralSummary(data);
      await loadReferralRebates();
      referrerCodeInput.value = "";
      toast({ title: "绑定成功", message: "", type: "success" });
    } catch (e) {
      toast({ title: "绑定失败", message: formatError(e), type: "error" });
    } finally {
      if (bindReferrerBtn) bindReferrerBtn.disabled = false;
    }
  }

  // === 事件绑定 ===
  qs("#logoutBtn").addEventListener("click", () => {
    clearToken();
    gotoLogin();
  });

  if (refreshReferralBtn) refreshReferralBtn.addEventListener("click", refreshReferral);
  if (bindReferrerBtn) bindReferrerBtn.addEventListener("click", bindReferrer);
  if (copyReferralBtn) {
    copyReferralBtn.addEventListener("click", async () => {
      const ok = await copyText(referralCodeEl?.textContent || "");
      toast({ title: ok ? "已复制" : "复制失败", message: "", type: ok ? "success" : "error" });
    });
  }
  if (copyReferralLinkBtn) {
    copyReferralLinkBtn.addEventListener("click", async () => {
      const ok = await copyText(referralLinkEl?.textContent || "");
      toast({ title: ok ? "已复制" : "复制失败", message: "", type: ok ? "success" : "error" });
    });
  }

  if (announcementCloseBtn) announcementCloseBtn.addEventListener("click", closeAnnouncement);
  if (announcementModal) {
    announcementModal.addEventListener("click", (e) => {
      if (e.target === announcementModal) closeAnnouncement();
    });
  }

  qs("#refreshMeBtn").addEventListener("click", async () => {
    try {
      await loadMe();
      toast({ title: "已刷新", message: "OK", type: "success" });
    } catch {}
  });

  const loadTxBtn = qs("#loadTxBtn");
  if (loadTxBtn) {
    loadTxBtn.addEventListener("click", () => loadWalletTx().catch((e) => toast({ title: "加载失败", message: formatError(e), type: "error" })));
  }

  const viewAllTxBtn = qs("#viewAllTxBtn");
  if (viewAllTxBtn) {
    viewAllTxBtn.addEventListener("click", () => setView("wallet"));
  }

  // 导航按钮
  navButtons.forEach((b) =>
    b.addEventListener("click", () => {
      if (b.classList.contains("hidden")) return;
      setView(b.dataset.nav);
    })
  );

  // === 初始化 ===
  (async () => {
    await loadMe();
    if (prefetchShopCache) prefetchShopCache();
    await loadAnnouncement();
    const stored = localStorage.getItem("dashboard_view") || "overview";
    const initial = stored === "admin" ? "overview" : stored;
    setView(initial);
    await loadWallet();
    await loadWalletTx();
    await loadReferralSummary();
    await loadReferralRebates();
  })().catch((e) => toast({ title: "初始化失败", message: formatError(e), type: "error" }));
})();

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
              <td>${esc(t.kind)}</td>
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
              <td>${esc(r.kind)}</td>
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

  // === 事件绑定 ===
  qs("#logoutBtn").addEventListener("click", () => {
    clearToken();
    gotoLogin();
  });

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
    await loadAnnouncement();
    const stored = localStorage.getItem("dashboard_view") || "overview";
    const initial = stored === "admin" ? "overview" : stored;
    setView(initial);
    await loadWallet();
    await loadWalletTx();
  })().catch((e) => toast({ title: "初始化失败", message: formatError(e), type: "error" }));
})();

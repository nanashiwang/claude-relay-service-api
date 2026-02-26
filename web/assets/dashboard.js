(function () {
  const {
    qs,
    qsa,
    apiRequest,
    requireAuth,
    clearToken,
    toast,
    formatError,
    escapeHtml: esc,
    prefetchShopCache,
  } = window.App;

  const state = {
    me: null,
  };

  const announcementAutoKey = "announcement_auto_open";
  const announcementModal = qs("#announcementModal");
  const announcementTitle = qs("#announcementTitle");
  const announcementContent = qs("#announcementContent");
  const announcementQrImg = qs("#announcementQrImg");
  const announcementQrEmpty = qs("#announcementQrEmpty");
  const announcementCloseBtn = qs("#announcementCloseBtn");
  const announcementEntryBtn = qs("#announcementEntryBtn");
  const agentEntryBtn = qs("#agentEntryBtn");

  const navButtons = qsa("[data-nav]");
  const viewEls = qsa("[data-view]");

  function normalizeView(name) {
    return name === "agent" ? "agent" : "overview";
  }

  function setView(name) {
    const target = normalizeView(name);
    navButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.nav === target));
    viewEls.forEach((view) => view.classList.toggle("hidden", view.dataset.view !== target));
    localStorage.setItem("dashboard_view", target);
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
      if (/^(-{3,}|_{3,}|={3,})$/.test(trimmed)) {
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

  async function openAnnouncement(options = {}) {
    if (!announcementModal) return;
    const silent = !!options.silent;

    try {
      const data = await apiRequest("/announcement");
      if (!data || data.active === false) {
        if (!silent) toast({ title: "暂无公告", message: "", type: "info" });
        return;
      }

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
      if (silent) {
        console.warn("Failed to load announcement", e);
        return;
      }
      toast({ title: "公告加载失败", message: formatError(e), type: "error" });
    }
  }

  async function maybeAutoOpenAnnouncement() {
    const shouldOpen = sessionStorage.getItem(announcementAutoKey);
    if (!shouldOpen) return;
    sessionStorage.removeItem(announcementAutoKey);
    await openAnnouncement({ silent: true });
  }

  async function loadMe() {
    state.me = await requireAuth();

    const userTextEl = qs("#userText");
    if (userTextEl) userTextEl.textContent = state.me.username;

    const adminTagEl = qs("#adminTag");
    if (adminTagEl) adminTagEl.classList.toggle("hidden", !state.me.is_admin);

    const adminEntryCard = qs("#adminEntryCard");
    if (adminEntryCard) adminEntryCard.classList.toggle("hidden", !state.me.is_admin);

    return state.me;
  }

  const logoutBtn = qs("#logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      clearToken();
      sessionStorage.removeItem(announcementAutoKey);
      gotoLogin();
    });
  }

  const refreshMeBtn = qs("#refreshMeBtn");
  if (refreshMeBtn) {
    refreshMeBtn.addEventListener("click", async () => {
      try {
        await loadMe();
        toast({ title: "已刷新", message: "", type: "success" });
      } catch (e) {
        toast({ title: "刷新失败", message: formatError(e), type: "error" });
      }
    });
  }

  if (announcementCloseBtn) announcementCloseBtn.addEventListener("click", closeAnnouncement);
  if (announcementModal) {
    announcementModal.addEventListener("click", (e) => {
      if (e.target === announcementModal) closeAnnouncement();
    });
  }
  if (announcementEntryBtn) {
    announcementEntryBtn.addEventListener("click", (e) => {
      e.preventDefault();
      openAnnouncement();
    });
  }
  if (agentEntryBtn) {
    agentEntryBtn.addEventListener("click", (e) => {
      e.preventDefault();
      setView("agent");
      const section = qs('[data-view="agent"]');
      if (section && section.scrollIntoView) {
        section.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  navButtons.forEach((btn) =>
    btn.addEventListener("click", () => {
      if (btn.classList.contains("hidden")) return;
      setView(btn.dataset.nav);
    })
  );

  (async () => {
    await loadMe();
    if (prefetchShopCache) prefetchShopCache();
    await maybeAutoOpenAnnouncement();
    const stored = localStorage.getItem("dashboard_view") || "overview";
    setView(stored);
  })().catch((e) => toast({ title: "初始化失败", message: formatError(e), type: "error" }));
})();

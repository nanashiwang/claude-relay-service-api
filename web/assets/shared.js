(function () {
  const API_PREFIX = "/api/v1";
  const TOKEN_KEY = "access_token";
  const SHOP_CACHE_KEY = "shop_cache_v1";
  const SHOP_CACHE_TS_KEY = "shop_cache_ts_v1";
  const SHOP_CACHE_TTL_MS = 5 * 60 * 1000;

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(token) {
    if (!token) localStorage.removeItem(TOKEN_KEY);
    else localStorage.setItem(TOKEN_KEY, token);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function safeJsonParse(text) {
    try {
      return text ? JSON.parse(text) : null;
    } catch {
      return text;
    }
  }

  function formatError(err) {
    if (!err) return "未知错误";
    if (typeof err === "string") return err;
    const msg = err instanceof Error ? err.message || "" : String(err);
    if (msg === "Failed to fetch") {
      if (typeof location !== "undefined" && location.protocol === "file:") {
        return "网络服务失败：请通过后端地址打开页面（例如 http://127.0.0.1:8000/），不要直接双击打开本地 html。";
      }
      return "网络服务失败：请确认后端服务正在运行、端口与当前页面一致。";
    }
    return msg || "未知错误";
  }

  function pretty(obj) {
    return JSON.stringify(obj, null, 2);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function apiRequest(path, { method = "GET", headers = {}, body } = {}) {
    const token = getToken();
    const finalHeaders = { ...headers };

    let finalBody = body;
    const isForm = typeof FormData !== "undefined" && body instanceof FormData;
    if (body && !isForm && typeof body === "object" && !(body instanceof Blob)) {
      finalHeaders["Content-Type"] = finalHeaders["Content-Type"] || "application/json";
      finalBody = JSON.stringify(body);
    }

    if (token) finalHeaders["Authorization"] = "Bearer " + token;

    const res = await fetch(API_PREFIX + path, { method, headers: finalHeaders, body: finalBody });
    const text = await res.text();
    const data = safeJsonParse(text);
    if (!res.ok) {
      let msg = text || res.statusText;
      if (data && typeof data === "object" && data.detail) {
        if (Array.isArray(data.detail)) {
          const parts = data.detail.map((item) => (item && item.msg ? item.msg : String(item)));
          msg = parts.filter(Boolean).join("；") || msg;
        } else {
          msg = data.detail;
        }
      }
      throw new Error(msg);
    }
    return data;
  }

  async function requireAuth({ redirectTo = "/" } = {}) {
    const token = getToken();
    if (!token) {
      if (redirectTo) window.location.href = redirectTo;
      throw new Error("未登录");
    }
    try {
      return await apiRequest("/auth/me");
    } catch (err) {
      clearToken();
      if (redirectTo) window.location.href = redirectTo;
      throw err;
    }
  }

  function ensureToastRoot() {
    let root = qs("#toast-root");
    if (!root) {
      root = document.createElement("div");
      root.id = "toast-root";
      root.className = "toast-root";
      document.body.appendChild(root);
    }
    return root;
  }

  function toast({ title = "提示", message = "", type = "info", timeoutMs = 3200 } = {}) {
    const root = ensureToastRoot();
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<div class="title"></div><div class="msg"></div>`;
    el.querySelector(".title").textContent = title;
    el.querySelector(".msg").textContent = message;
    root.appendChild(el);

    const close = () => {
      if (!el.isConnected) return;
      el.style.opacity = "0";
      el.style.transform = "translateY(2px)";
      setTimeout(() => el.remove(), 180);
    };

    setTimeout(close, timeoutMs);
    el.addEventListener("click", close);
  }

  function moneyFromCents(cents, currency = "CNY") {
    const n = Number(cents || 0) / 100;
    return `${n.toFixed(2)} ${currency}`;
  }

  function saveShopCache(data) {
    try {
      if (!data) return;
      localStorage.setItem(SHOP_CACHE_KEY, JSON.stringify(data));
      localStorage.setItem(SHOP_CACHE_TS_KEY, String(Date.now()));
    } catch {}
  }

  function loadShopCache() {
    try {
      const raw = localStorage.getItem(SHOP_CACHE_KEY);
      const ts = Number(localStorage.getItem(SHOP_CACHE_TS_KEY) || "0");
      if (!raw || !ts) return null;
      if (Date.now() - ts > SHOP_CACHE_TTL_MS) return null;
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object") return null;
      return data;
    } catch {
      return null;
    }
  }

  function clearShopCache() {
    try {
      localStorage.removeItem(SHOP_CACHE_KEY);
      localStorage.removeItem(SHOP_CACHE_TS_KEY);
    } catch {}
  }

  async function prefetchShopCache() {
    try {
      const data = await apiRequest("/products/by-category-with-inventory");
      saveShopCache({
        codex: data?.codex || [],
        gemini: data?.gemini || [],
        claude: data?.claude || [],
        inventory: data?.inventory || {},
      });
      return data;
    } catch {
      return null;
    }
  }

  window.App = {
    API_PREFIX,
    qs,
    qsa,
    getToken,
    setToken,
    clearToken,
    apiRequest,
    requireAuth,
    pretty,
    escapeHtml,
    toast,
    formatError,
    moneyFromCents,
    saveShopCache,
    loadShopCache,
    clearShopCache,
    prefetchShopCache,
  };
})();

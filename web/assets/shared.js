(function () {
  const API_PREFIX = "/api/v1";
  const TOKEN_KEY = "access_token";

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
      const msg = data && typeof data === "object" && data.detail ? data.detail : text || res.statusText;
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
  };
})();

(function () {
  const { qs, qsa, apiRequest, setToken, getToken, toast, formatError, prefetchShopCache } = window.App;

  const loginTab = qs('[data-tab="login"]');
  const registerTab = qs('[data-tab="register"]');
  const loginPanel = qs("#panel-login");
  const registerPanel = qs("#panel-register");

  const loginBtn = qs("#loginBtn");
  const registerBtn = qs("#registerBtn");
  const switchToLoginBtn = qs("#switchToLoginBtn");

  const loginUsername = qs("#loginUsername");
  const loginPassword = qs("#loginPassword");
  const loginCaptcha = qs("#loginCaptcha");
  const regUsername = qs("#regUsername");
  const regPassword = qs("#regPassword");
  const regCaptcha = qs("#regCaptcha");
  const captchaImages = qsa("[data-captcha-image]");
  const captchaRefreshBtns = qsa("[data-captcha-refresh]");

  let captchaState = null;

  function setActiveTab(name) {
    const isLogin = name === "login";
    loginTab.classList.toggle("active", isLogin);
    registerTab.classList.toggle("active", !isLogin);
    loginPanel.classList.toggle("hidden", !isLogin);
    registerPanel.classList.toggle("hidden", isLogin);
  }

  function toDashboard() {
    window.location.href = "/web/dashboard.html";
  }

  function isCaptchaExpired() {
    if (!captchaState || !captchaState.expires) return true;
    return Math.floor(Date.now() / 1000) >= captchaState.expires;
  }

  async function loadCaptcha() {
    try {
      const data = await apiRequest("/auth/captcha");
      captchaState = {
        id: data.captcha_id,
        token: data.captcha_token,
        expires: data.captcha_expires,
      };
      captchaImages.forEach((img) => {
        if (!img) return;
        img.src = data.captcha_svg || "";
      });
      if (loginCaptcha) loginCaptcha.value = "";
      if (regCaptcha) regCaptcha.value = "";
    } catch (e) {
      console.warn("Failed to load captcha", e);
      toast({ title: "验证码加载失败", message: formatError(e), type: "error" });
    }
  }

  async function requireCaptchaInput() {
    const input = loginPanel.classList.contains("hidden") ? regCaptcha : loginCaptcha;
    const code = (input && input.value ? input.value : "").trim();
    if (!code) {
      toast({ title: "请输入验证码", message: "验证码不能为空", type: "error" });
      return null;
    }
    if (!captchaState || !captchaState.token || isCaptchaExpired()) {
      await loadCaptcha();
      toast({ title: "验证码已刷新", message: "请重新输入验证码", type: "info" });
      return null;
    }
    return {
      code,
      captcha_id: captchaState.id,
      captcha_token: captchaState.token,
      captcha_expires: captchaState.expires,
    };
  }

  async function doLogin() {
    const username = (loginUsername.value || "").trim();
    const password = loginPassword.value || "";
    if (!username || !password) {
      toast({ title: "请填写完整", message: "用户名和密码不能为空", type: "error" });
      return;
    }
    const captcha = await requireCaptchaInput();
    if (!captcha) return;

    loginBtn.disabled = true;
    loginBtn.textContent = "登录中...";
    try {
      const { code, ...captchaPayload } = captcha;
      const data = await apiRequest("/auth/login", {
        method: "POST",
        body: { username, password, captcha_code: code, ...captchaPayload },
      });
      setToken(data.access_token);
      if (prefetchShopCache) prefetchShopCache();
      toast({ title: "登录成功", message: "正在进入控制台...", type: "success" });
      setTimeout(toDashboard, 450);
    } catch (e) {
      toast({ title: "登录失败", message: formatError(e), type: "error" });
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = "登录";
      loadCaptcha().catch(() => {});
    }
  }

  async function doRegister() {
    const username = (regUsername.value || "").trim();
    const password = regPassword.value || "";
    if (!username || !password) {
      toast({ title: "请填写完整", message: "用户名和密码不能为空", type: "error" });
      return;
    }
    const captcha = await requireCaptchaInput();
    if (!captcha) return;

    registerBtn.disabled = true;
    registerBtn.textContent = "注册中...";
    try {
      await apiRequest("/auth/register", { method: "POST", body: { username, password } });
      toast({ title: "注册成功", message: "已为你自动登录", type: "success" });
      const { code, ...captchaPayload } = captcha;
      const data = await apiRequest("/auth/login", {
        method: "POST",
        body: { username, password, captcha_code: code, ...captchaPayload },
      });
      setToken(data.access_token);
      if (prefetchShopCache) prefetchShopCache();
      setTimeout(toDashboard, 450);
    } catch (e) {
      toast({ title: "注册失败", message: formatError(e), type: "error" });
    } finally {
      registerBtn.disabled = false;
      registerBtn.textContent = "注册";
      loadCaptcha().catch(() => {});
    }
  }

  async function tryAutoRedirect() {
    const token = getToken();
    if (!token) return false;
    try {
      await apiRequest("/auth/me");
      toDashboard();
      return true;
    } catch {
      setToken("");
      return false;
    }
  }

  loginTab.addEventListener("click", () => setActiveTab("login"));
  registerTab.addEventListener("click", () => setActiveTab("register"));
  if (switchToLoginBtn) switchToLoginBtn.addEventListener("click", () => setActiveTab("login"));

  loginBtn.addEventListener("click", doLogin);
  registerBtn.addEventListener("click", doRegister);
  captchaRefreshBtns.forEach((btn) => btn.addEventListener("click", () => loadCaptcha()));
  captchaImages.forEach((img) => img.addEventListener("click", () => loadCaptcha()));
  qsa('input[type="password"]').forEach((el) => {
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      if (!loginPanel.classList.contains("hidden")) doLogin();
      else doRegister();
    });
  });

  (async () => {
    setActiveTab("login");
    const redirected = await tryAutoRedirect();
    if (!redirected) {
      await loadCaptcha();
    }
  })();
})();

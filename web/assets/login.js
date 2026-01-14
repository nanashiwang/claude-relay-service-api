(function () {
  const { qs, qsa, apiRequest, setToken, getToken, toast, formatError } = window.App;

  const loginTab = qs('[data-tab="login"]');
  const registerTab = qs('[data-tab="register"]');
  const loginPanel = qs("#panel-login");
  const registerPanel = qs("#panel-register");

  const loginBtn = qs("#loginBtn");
  const registerBtn = qs("#registerBtn");
  const switchToLoginBtn = qs("#switchToLoginBtn");

  const loginUsername = qs("#loginUsername");
  const loginPassword = qs("#loginPassword");
  const regUsername = qs("#regUsername");
  const regPassword = qs("#regPassword");

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

  async function tryAutoRedirect() {
    const token = getToken();
    if (!token) return;
    try {
      await apiRequest("/auth/me");
      toDashboard();
    } catch {
      setToken("");
    }
  }

  async function doLogin() {
    const username = (loginUsername.value || "").trim();
    const password = loginPassword.value || "";
    if (!username || !password) {
      toast({ title: "请填写完整", message: "用户名和密码不能为空", type: "error" });
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "登录中...";
    try {
      const data = await apiRequest("/auth/login", { method: "POST", body: { username, password } });
      setToken(data.access_token);
      toast({ title: "登录成功", message: "正在进入控制台...", type: "success" });
      setTimeout(toDashboard, 450);
    } catch (e) {
      toast({ title: "登录失败", message: formatError(e), type: "error" });
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = "登录";
    }
  }

  async function doRegister() {
    const username = (regUsername.value || "").trim();
    const password = regPassword.value || "";
    if (!username || !password) {
      toast({ title: "请填写完整", message: "用户名和密码不能为空", type: "error" });
      return;
    }

    registerBtn.disabled = true;
    registerBtn.textContent = "注册中...";
    try {
      await apiRequest("/auth/register", { method: "POST", body: { username, password } });
      toast({ title: "注册成功", message: "已为你自动登录", type: "success" });
      const data = await apiRequest("/auth/login", { method: "POST", body: { username, password } });
      setToken(data.access_token);
      setTimeout(toDashboard, 450);
    } catch (e) {
      toast({ title: "注册失败", message: formatError(e), type: "error" });
    } finally {
      registerBtn.disabled = false;
      registerBtn.textContent = "注册";
    }
  }

  loginTab.addEventListener("click", () => setActiveTab("login"));
  registerTab.addEventListener("click", () => setActiveTab("register"));
  if (switchToLoginBtn) switchToLoginBtn.addEventListener("click", () => setActiveTab("login"));

  loginBtn.addEventListener("click", doLogin);
  registerBtn.addEventListener("click", doRegister);

  qsa('input[type="password"]').forEach((el) => {
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      if (!loginPanel.classList.contains("hidden")) doLogin();
      else doRegister();
    });
  });

  setActiveTab("login");
  tryAutoRedirect();
})();

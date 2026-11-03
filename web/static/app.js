(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const state = {
    config: null,
    profile: null,
    busy: false,
  };

  const loginCard = $("loginCard");
  const appCard = $("appCard");
  const banner = $("resultBanner");
  const statusPill = $("statusPill");
  const loginForm = $("loginForm");
  const loginBtn = $("loginBtn");
  const loginError = $("loginError");
  const runForm = $("runForm");
  const runBtn = $("runBtn");
  const paceHint = $("paceHint");
  const mapHint = $("mapHint");

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = null;
    }

    if (!response.ok) {
      const detail = data && (data.detail || data.error);
      const error = new Error(
        typeof detail === "string" && detail ? detail : `请求失败（${response.status}）`
      );
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function showBanner(kind, text) {
    banner.className = `banner ${kind}`;
    banner.textContent = text;
    banner.hidden = false;
  }

  function clearBanner() {
    banner.hidden = true;
    banner.textContent = "";
    banner.className = "banner";
  }

  function setBusy(button, busy, label) {
    if (busy) {
      if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent;
      }
      button.textContent = label;
      button.disabled = true;
    } else {
      button.textContent = button.dataset.originalText || button.textContent;
      button.disabled = false;
    }
  }

  function showLogin() {
    state.profile = null;
    loginCard.hidden = false;
    appCard.hidden = true;
    statusPill.textContent = "未登录";
    statusPill.classList.remove("online");
    $("password").value = "";
    $("accessCode").value = "";
    loginError.textContent = "";
    mapHint.textContent = "";
    mapHint.classList.remove("warn");
  }

  function setMapOptions(maps, defaultKey) {
    const select = $("mapSelect");
    select.textContent = "";
    for (const item of maps || []) {
      const option = document.createElement("option");
      option.value = item.key;
      option.textContent = item.name;
      select.appendChild(option);
    }
    if (defaultKey) {
      select.value = defaultKey;
    }
  }

  function updateMapHint(info) {
    if (!info || !info.maps) {
      mapHint.textContent = "";
      return;
    }
    const count = info.maps.length;
    if (!info.map_matched) {
      mapHint.textContent = "未匹配到账号所属校区，已显示全部地图，请手动选择";
      mapHint.classList.add("warn");
    } else if (count > 1) {
      mapHint.textContent = `已按账号匹配到 ${count} 个校区，请确认`;
      mapHint.classList.remove("warn");
    } else {
      mapHint.textContent = "已根据账号自动选择校区";
      mapHint.classList.remove("warn");
    }
  }

  function showApp(profile, mapInfo) {
    state.profile = profile;
    loginCard.hidden = true;
    appCard.hidden = false;
    statusPill.textContent = "已登录";
    statusPill.classList.add("online");

    const name = profile.studentName || "同学";
    $("studentName").textContent = name;
    $("schoolName").textContent = profile.schoolName || "—";
    $("avatar").textContent = name.slice(0, 1);

    if (mapInfo && mapInfo.maps) {
      setMapOptions(mapInfo.maps, mapInfo.default_map);
      updateMapHint(mapInfo);
    }
    updatePaceHint();
  }

  function updatePaceHint() {
    if (!state.config) return;
    const distance = Number($("distance").value);
    const time = Number($("time").value);
    if (!distance || !time) {
      paceHint.textContent = "";
      paceHint.classList.remove("too-fast");
      return;
    }
    const pace = (time / distance) * 1000;
    paceHint.textContent = `预计配速 ${pace.toFixed(2)} 分钟/公里`;
    paceHint.classList.toggle("too-fast", pace < 6);
    if (pace < 6) {
      paceHint.textContent += "，过快会被拒绝提交";
    }
  }

  function applyConfig(config) {
    state.config = config;

    const distance = $("distance");
    distance.min = config.distance.min;
    distance.max = config.distance.max;
    distance.value = config.distance.default;

    const time = $("time");
    time.min = config.time.min;
    time.max = config.time.max;
    time.value = config.time.default;

    setMapOptions(config.maps, null);

    $("accessCodeRow").hidden = !config.access_code_required;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;

    const phone = $("phone").value.trim();
    const password = $("password").value;
    if (!phone || !password) {
      loginError.textContent = "请输入手机号和密码";
      return;
    }

    loginError.textContent = "";
    state.busy = true;
    setBusy(loginBtn, true, "登录中…");

    try {
      const data = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({
          phone,
          password,
          access_code: $("accessCode").value || null,
          disclaimer_accepted: true,
        }),
      });
      clearBanner();
      showApp(data.profile, data);
    } catch (error) {
      loginError.textContent = error.message;
    } finally {
      $("password").value = "";
      state.busy = false;
      setBusy(loginBtn, false);
    }
  });

  runForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || !state.config) return;

    const distance = Number($("distance").value);
    const time = Number($("time").value);
    const limits = state.config;

    if (
      !Number.isInteger(distance) ||
      distance < limits.distance.min ||
      distance > limits.distance.max
    ) {
      showBanner("error", `里程需在 ${limits.distance.min}–${limits.distance.max} 米之间`);
      return;
    }
    if (
      !Number.isInteger(time) ||
      time < limits.time.min ||
      time > limits.time.max
    ) {
      showBanner("error", `时长需在 ${limits.time.min}–${limits.time.max} 分钟之间`);
      return;
    }

    clearBanner();
    state.busy = true;
    setBusy(runBtn, true, "生成轨迹并提交中…");

    try {
      const data = await api("/api/run", {
        method: "POST",
        body: JSON.stringify({
          distance,
          time,
          map: $("mapSelect").value,
        }),
      });

      if (data.logged_out) {
        showLogin();
      }
      showBanner(
        data.ok ? "success" : "error",
        data.ok ? data.result : data.error
      );
    } catch (error) {
      if (error.status === 401) {
        showLogin();
        showBanner("error", "会话已过期，请重新登录");
      } else {
        showBanner("error", error.message);
      }
    } finally {
      state.busy = false;
      setBusy(runBtn, false);
    }
  });

  $("logoutBtn").addEventListener("click", async () => {
    if (state.busy) return;
    state.busy = true;
    setBusy($("logoutBtn"), true, "退出中…");
    try {
      await api("/api/logout", { method: "POST" });
    } catch (_) {
      // 会话可能已过期，本地状态照常清理
    } finally {
      state.busy = false;
      setBusy($("logoutBtn"), false);
      showLogin();
      showBanner("success", "已退出登录，本次 token 已销毁");
    }
  });

  $("distance").addEventListener("input", updatePaceHint);
  $("time").addEventListener("input", updatePaceHint);

  async function init() {
    try {
      const config = await api("/api/config");
      applyConfig(config);
    } catch (error) {
      showBanner("error", `无法加载配置：${error.message}`);
      return;
    }

    try {
      const me = await api("/api/me");
      showApp(me.profile, me);
    } catch (_) {
      showLogin();
    }
  }

  const overlay = $("disclaimerOverlay");
  const closedScreen = $("closedScreen");
  const acceptBtn = $("disclaimerAccept");
  const declineBtn = $("disclaimerDecline");
  let started = false;

  function startApp() {
    if (started) return;
    started = true;
    init();
  }

  acceptBtn.addEventListener("click", () => {
    overlay.hidden = true;
    document.body.classList.remove("modal-open");
    startApp();
    $("phone").focus();
  });

  declineBtn.addEventListener("click", () => {
    overlay.hidden = true;
    document.body.classList.remove("modal-open");
    document.querySelector(".page").hidden = true;
    closedScreen.hidden = false;

    // 浏览器通常禁止脚本关闭非脚本打开的标签页；
    // 关闭失败时停留在“已停止使用”页面。
    window.close();
  });

  overlay.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    if (event.shiftKey && document.activeElement === declineBtn) {
      event.preventDefault();
      acceptBtn.focus();
    } else if (!event.shiftKey && document.activeElement === acceptBtn) {
      event.preventDefault();
      declineBtn.focus();
    }
  });

  acceptBtn.focus();
})();

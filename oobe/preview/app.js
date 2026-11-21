"use strict";

const $ = (id) => document.getElementById(id);
const pages = [...document.querySelectorAll(".page")];
const pageStage = $("page-stage");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const TITLES = ["第 1 步，欢迎", "第 2 步，网络", "第 3 步，账户", "第 4 步，确认", "正在准备", "设置完成"];
const NEXT_LABELS = ["开始设置", "继续", "继续", "进入桌面", "", ""];

const WIFI_NETWORKS = [
  { ssid: "Mocha-5G", secured: true, strength: 3 },
  { ssid: "Rainy_Room", secured: true, strength: 2 },
  { ssid: "Moze-Guest", secured: false, strength: 3 },
  { ssid: "Cafe Latte", secured: true, strength: 1 },
];

const BT_DEVICES = [
  { id: "mx", name: "MX Master 3S", type: "鼠标", initial: "M" },
  { id: "k3", name: "Keychron K3", type: "键盘", initial: "K" },
  { id: "flex", name: "SoundLink Flex", type: "音箱", initial: "S" },
  { id: "wh", name: "WH-1000XM4", type: "耳机", initial: "W" },
];

const state = {
  page: 0,
  activeInput: null,
  shift: false,
  wifi: { on: true, connected: null, connecting: null, joinFor: null, draft: "", error: "" },
  bluetooth: { on: true, paired: new Set(), busy: null, scanning: true, expanded: false },
};

let applying = false;

/* ----------------------------------------------------------------- intro */

(() => {
  const intro = $("intro");
  const canvas = $("intro-canvas");
  const stage = document.querySelector(".stage");
  if (!intro || !canvas) return;

  if (reduceMotion) {
    intro.remove();
    return;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    intro.remove();
    return;
  }

  stage?.classList.add("intro-active");

  const labels = [...document.querySelectorAll("#intro-greetings span")].map((el, index) => {
    const lat = (Number(el.dataset.lat) * Math.PI) / 180;
    const lon = (Number(el.dataset.lon) * Math.PI) / 180;
    const cos = Math.cos(lat);
    return {
      el,
      nx: cos * Math.sin(lon),
      ny: Math.sin(lat),
      nz: -cos * Math.cos(lon),
      delay: 0.35 + index * 0.12,
      phase: index * 1.7,
      speed: 0.24 + Math.random() * 0.18,
      driftX: 4 + Math.random() * 3,
      driftY: 4 + Math.random() * 3,
    };
  });
  const enter = $("intro-enter");
  const COUNT = 2200;
  const EXIT = 1000;

  let width = 0;
  let height = 0;
  let cx = 0;
  let cy = 0;
  let radius = 160;
  let particles = [];
  let raf = 0;
  let closed = false;
  let leaving = false;
  let exitStart = 0;
  let resizeTimer = 0;
  const start = performance.now();

  const reset = () => {
    width = window.innerWidth;
    height = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx = width / 2;
    cy = height * 0.55;
    radius = Math.min(width, height) * (width < 620 ? 0.28 : 0.22);
    if (enter) {
      const buttonTop = Math.min(cy + radius + (width < 620 ? 78 : 92), height - 72);
      enter.style.top = `${buttonTop}px`;
    }

    const golden = Math.PI * (3 - Math.sqrt(5));
    particles = [];
    for (let index = 0; index < COUNT; index += 1) {
      const v = 1 - (index / (COUNT - 1)) * 2;
      const ring = Math.sqrt(Math.max(0, 1 - v * v));
      const theta = golden * index;
      particles.push({
        nx: Math.cos(theta) * ring,
        ny: v,
        nz: Math.sin(theta) * ring,
        size: 0.7 + Math.random() * 1.4,
        phase: Math.random() * Math.PI * 2,
        drift: 0.4 + Math.random() * 0.9,
      });
    }
  };

  const project = (particle, angle) => {
    const tilt = -0.36;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const x = particle.nx * cos - particle.nz * sin;
    const z = particle.nx * sin + particle.nz * cos;
    const y = -(particle.ny * Math.cos(tilt) - z * Math.sin(tilt));
    const depth = particle.ny * Math.sin(tilt) + z * Math.cos(tilt);
    const persp = 1 / (1 + depth * 0.3);
    return {
      x: cx + x * radius * persp,
      y: cy + y * radius * persp,
      depth,
    };
  };

  const draw = (now) => {
    if (closed) return;
    const elapsed = (now - start) / 1000;
    const exitProgress = leaving ? Math.min(1, (now - exitStart) / EXIT) : 0;
    const exitEase = exitProgress < 0.5 ? 2 * exitProgress ** 2 : 1 - (-2 * exitProgress + 2) ** 2 / 2;
    const appear = Math.min(1, elapsed / 0.7);

    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = "lighter";

    const coreAlpha = 0.17 * appear * (1 - exitEase);
    if (coreAlpha > 0.001) {
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 1.55);
      core.addColorStop(0, `rgba(150, 226, 248, ${(coreAlpha * 1.15).toFixed(3)})`);
      core.addColorStop(0.55, `rgba(110, 190, 226, ${coreAlpha.toFixed(3)})`);
      core.addColorStop(1, "rgba(110, 190, 226, 0)");
      ctx.fillStyle = core;
      ctx.fillRect(cx - radius * 1.8, cy - radius * 1.8, radius * 3.6, radius * 3.6);
    }

    const rotation = elapsed * 0.2;
    for (const particle of particles) {
      const sphere = project(particle, rotation);
      const front = Math.max(0, Math.min(1, (1 - sphere.depth) / 2));
      let alpha = (0.12 + 0.7 * front) * appear;
      let size = particle.size * (0.45 + front * 1.15);
      let x = sphere.x;
      let y = sphere.y;
      let tint = front > 0.55 ? "228, 246, 255" : "150, 214, 238";

      if (leaving) {
        const dx = (sphere.x - cx) / (radius || 1);
        const dy = (sphere.y - cy) / (radius || 1);
        const distance = radius * exitEase * (0.5 + particle.drift * 1.2);
        const swirl = Math.sin(particle.phase) * exitEase * 24;
        x = sphere.x + dx * distance - dy * swirl + Math.sin(elapsed * 2.2 + particle.phase) * exitEase * 6;
        y = sphere.y + dy * distance + dx * swirl - exitEase * radius * 0.5;
        alpha *= 1 - exitEase;
        size *= 1 - exitEase * 0.3;
        tint = "214, 241, 255";
      } else {
        alpha *= 0.78 + 0.22 * Math.sin(elapsed * 2.2 + particle.phase);
      }

      ctx.fillStyle = `rgba(${tint}, ${alpha.toFixed(3)})`;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.5, size * 0.5), 0, Math.PI * 2);
      ctx.fill();
    }

    for (const label of labels) {
      const point = project(label, 0);
      const front = Math.max(0, Math.min(1, (1 - point.depth) / 2));
      const reveal = Math.max(0, Math.min(1, (elapsed - label.delay) / 0.7));
      const opacity = (0.55 + 0.45 * front) * reveal * (1 - exitEase);
      const scale = 0.8 + front * 0.35;
      const floatX =
        Math.sin(elapsed * label.speed + label.phase) * label.driftX +
        Math.sin(elapsed * label.speed * 0.43 + label.phase * 1.7) * label.driftX * 0.45;
      const floatY =
        Math.cos(elapsed * label.speed * 0.78 + label.phase) * label.driftY +
        Math.sin(elapsed * label.speed * 0.31 + label.phase * 2.1) * label.driftY * 0.4;
      const sway = Math.sin(elapsed * label.speed * 0.5 + label.phase) * 0.9;
      const breathe = 1 + Math.sin(elapsed * label.speed * 0.36 + label.phase) * 0.015;
      const style = label.el.style;
      style.left = `${point.x + floatX}px`;
      style.top = `${point.y + floatY}px`;
      style.transform = `translate(-50%, -50%) scale(${(scale * breathe).toFixed(3)}) rotate(${sway.toFixed(2)}deg)`;
      style.opacity = opacity.toFixed(3);
      style.zIndex = String(2 + Math.round(front * 10));
    }

    raf = requestAnimationFrame(draw);
  };

  const beginExit = () => {
    if (leaving || closed) return;
    leaving = true;
    exitStart = performance.now();
    intro.classList.add("leaving");
    setTimeout(() => {
      intro.classList.add("hide");
      stage?.classList.remove("intro-active");
      stage?.classList.add("setup-enter");
    }, 500);
    setTimeout(() => {
      closed = true;
      cancelAnimationFrame(raf);
      intro.remove();
      document.querySelector(".page:not([hidden]) h1")?.focus({ preventScroll: true });
    }, 1500);
  };

  enter?.addEventListener("click", beginExit);

  reset();
  raf = requestAnimationFrame(draw);

  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!closed) reset();
    }, 160);
  });
})();

/* ------------------------------------------------------- background video */

(() => {
  const video = $("bg-video");
  if (!video) return;
  const source = video.querySelector("source");
  const fallback = () => document.body.classList.add("no-video");
  video.addEventListener("error", fallback);
  source?.addEventListener("error", fallback);

  if (reduceMotion) {
    video.autoplay = false;
    video.removeAttribute("autoplay");
    video.addEventListener("loadedmetadata", () => {
      try {
        video.currentTime = 0.1;
      } catch (_) {
        /* some browsers refuse seeking before data is ready */
      }
      video.pause();
    }, { once: true });
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      video.pause();
    } else if (!reduceMotion) {
      video.play().catch(() => {});
    }
  });
})();

/* ---------------------------------------------------------------- helpers */

function announce(message, tone = "info") {
  const feedback = $("feedback");
  feedback.textContent = message;
  if (tone === "error") feedback.dataset.tone = "error";
  else delete feedback.dataset.tone;
}

function clearFeedback() {
  announce("");
}

function setActiveInput(input) {
  state.activeInput = input;
  if (input && !$("keyboard").hidden) {
    requestAnimationFrame(() => {
      input.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    });
  }
}

function emptyRow(text) {
  const item = document.createElement("li");
  item.className = "empty";
  item.textContent = text;
  return item;
}

/* ------------------------------------------------------------ preferences */

const choiceWidgets = [];

function setupChoice(selectId) {
  const select = $(selectId);
  const trigger = $(`${selectId}-trigger`);
  const menu = $(`${selectId}-menu`);
  const value = $(`${selectId}-value`);
  if (!select || !trigger || !menu || !value) return null;

  const baseLabel = trigger.getAttribute("aria-label") || "";
  const svgNS = "http://www.w3.org/2000/svg";

  const sync = () => {
    const selected = select.selectedOptions[0] ?? select.options[0];
    if (!selected) return;
    value.textContent = selected.textContent;
    trigger.setAttribute("aria-label", `${baseLabel}，当前 ${selected.textContent}`);
    for (const option of menu.querySelectorAll(".choice-option")) {
      option.setAttribute("aria-selected", String(option.dataset.value === select.value));
    }
  };

  const render = () => {
    menu.replaceChildren();
    for (const native of select.options) {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "choice-option";
      option.dataset.value = native.value;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(native.value === select.value));

      const label = document.createElement("span");
      label.textContent = native.textContent;

      const check = document.createElementNS(svgNS, "svg");
      check.setAttribute("class", "icon option-check");
      check.setAttribute("aria-hidden", "true");
      const use = document.createElementNS(svgNS, "use");
      use.setAttribute("href", "#icon-check");
      check.append(use);

      option.append(label, check);
      option.addEventListener("click", () => {
        select.value = native.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        sync();
        closeChoices(true);
        trigger.focus({ preventScroll: true });
      });
      menu.append(option);
    }
    sync();
  };

  trigger.addEventListener("click", (event) => {
    if (menu.hidden) openChoice(selectId, event.detail === 0);
    else closeChoices(true);
  });

  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openChoice(selectId, true);
    }
  });

  menu.addEventListener("keydown", (event) => {
    const options = [...menu.querySelectorAll(".choice-option")];
    const index = options.indexOf(document.activeElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      options[(index + step + options.length) % options.length]?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeChoices(true);
    }
  });

  render();
  return { select, trigger, menu };
}

function setupChoices() {
  for (const id of ["locale", "timezone"]) {
    const widget = setupChoice(id);
    if (widget) choiceWidgets.push(widget);
  }
}

function closeChoices(focusTrigger = false) {
  for (const widget of choiceWidgets) {
    if (widget.menu.hidden) continue;
    widget.menu.hidden = true;
    widget.trigger.setAttribute("aria-expanded", "false");
    widget.menu.closest(".choice")?.classList.remove("open");
    if (focusTrigger) widget.trigger.focus({ preventScroll: true });
  }
}

function openChoice(selectId, focusOption = false) {
  const widget = choiceWidgets.find((entry) => entry.select.id === selectId);
  if (!widget) return;
  closeChoices();
  widget.menu.hidden = false;
  widget.trigger.setAttribute("aria-expanded", "true");
  widget.menu.closest(".choice")?.classList.add("open");
  widget.menu.scrollIntoView({ block: "nearest", inline: "nearest" });
  if (focusOption) {
    const selected = widget.menu.querySelector('[aria-selected="true"]') ?? widget.menu.querySelector(".choice-option");
    selected?.focus({ preventScroll: true });
  }
}

document.addEventListener("pointerdown", (event) => {
  if (!(event.target instanceof Element) || event.target.closest(".choice")) return;
  closeChoices();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeChoices();
});

/* ------------------------------------------------------------------- wifi */

function wifiStatusText() {
  const wifi = state.wifi;
  if (wifi.available === false) return "暂未检测到 Wi-Fi 网卡";
  if (!wifi.on) return "Wi-Fi 已关闭";
  if (wifi.connecting) return `正在连接 ${wifi.connecting}…`;
  if (wifi.connected) return `已连接到 ${wifi.connected}`;
  return `发现 ${WIFI_NETWORKS.length} 个可用网络`;
}

function renderWifi() {
  const wifi = state.wifi;
  $("wifi-status").textContent = wifiStatusText();
  $("wifi-toggle").checked = wifi.on;
  $("wifi-toggle").disabled = wifi.available === false;

  const list = $("wifi-list");
  list.replaceChildren();
  if (wifi.available === false) {
    list.append(emptyRow("可先继续设置，稍后在系统设置中联网"));
    return;
  }

  if (!wifi.on) {
    list.append(emptyRow("Wi-Fi 已关闭，打开开关后会重新搜索网络"));
    return;
  }

  for (const network of WIFI_NETWORKS) {
    const isConnected = wifi.connected === network.ssid;
    const isConnecting = wifi.connecting === network.ssid;

    const item = document.createElement("li");
    item.className = "device-item";
    item.classList.toggle("is-connected", isConnected);
    item.classList.toggle("is-busy", isConnecting);

    const row = document.createElement("button");
    row.type = "button";
    row.className = "device-row";
    row.disabled = wifi.connecting !== null;

    const signal = document.createElement("span");
    signal.className = "signal";
    signal.dataset.level = String(network.strength);
    signal.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 3; index += 1) signal.append(document.createElement("i"));

    const main = document.createElement("span");
    main.className = "device-main";
    const name = document.createElement("span");
    name.className = "device-name";
    name.textContent = network.ssid;
    main.append(name);

    const side = document.createElement("span");
    side.className = "device-side";
    if (isConnected) {
      side.classList.add("ok");
      side.textContent = "✓";
    } else if (isConnecting) {
      side.innerHTML = '<span class="mini-spin" aria-hidden="true"></span>';
    } else if (network.secured) {
      side.innerHTML = '<span class="lock" aria-hidden="true"></span>';
    } else {
      side.classList.add("chip");
      side.textContent = "开放";
    }

    row.append(signal, main, side);
    row.setAttribute(
      "aria-label",
      `${network.ssid}，${network.secured ? "加密网络" : "开放网络"}，${
        isConnected ? "已连接" : isConnecting ? "正在连接" : "点击连接"
      }`
    );
    row.addEventListener("click", () => chooseWifi(network));
    item.append(row);

    if (wifi.joinFor === network.ssid) item.append(buildWifiJoin(network));
    list.append(item);
  }

  // A re-render can remove the Wi-Fi password field from the document; drop
  // the stale typing target so the on-screen keyboard cannot type into nothing.
  if (state.activeInput && !state.activeInput.isConnected) {
    state.activeInput = null;
    if (!$("keyboard").hidden) setKeyboard(false);
  }
}

function buildWifiJoin(network) {
  const wrap = document.createElement("div");
  wrap.className = "wifi-join";

  const input = document.createElement("input");
  input.type = "password";
  input.id = "wifi-password";
  input.placeholder = "输入 Wi-Fi 密码";
  input.maxLength = 63;
  input.value = state.wifi.draft;
  input.setAttribute("autocomplete", "off");
  input.setAttribute("aria-label", `${network.ssid} 的 Wi-Fi 密码`);
  input.setAttribute("aria-describedby", "wifi-join-error");

  const error = document.createElement("p");
  error.className = "inline-error";
  error.id = "wifi-join-error";
  error.setAttribute("aria-live", "polite");
  error.textContent = state.wifi.error;

  input.addEventListener("focus", () => setActiveInput(input));
  input.addEventListener("input", () => {
    state.wifi.draft = input.value;
    state.wifi.error = "";
    error.textContent = "";
    input.removeAttribute("aria-invalid");
    clearFeedback();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitWifiPassword(network);
    }
  });

  const join = document.createElement("button");
  join.type = "button";
  join.className = "mini-primary";
  join.textContent = "加入";
  join.addEventListener("click", () => submitWifiPassword(network));

  const row = document.createElement("div");
  row.className = "wifi-join-row";
  row.append(input, join);
  wrap.append(row, error);
  return wrap;
}

function chooseWifi(network) {
  const wifi = state.wifi;
  if (!wifi.on || wifi.connecting) return;
  if (wifi.connected === network.ssid) return;
  if (wifi.joinFor === network.ssid) {
    $("wifi-password")?.focus({ preventScroll: true });
    return;
  }
  wifi.error = "";
  wifi.draft = "";
  if (network.secured) {
    wifi.joinFor = network.ssid;
    renderWifi();
    requestAnimationFrame(() => $("wifi-password")?.focus({ preventScroll: true }));
  } else {
    connectWifi(network);
  }
}

function submitWifiPassword(network) {
  const input = $("wifi-password");
  const value = input ? input.value : state.wifi.draft;
  if (value.length < 8) {
    state.wifi.error = "密码至少需要 8 个字符";
    state.wifi.draft = value;
    if (input) {
      input.setAttribute("aria-invalid", "true");
      input.focus({ preventScroll: true });
      const error = $("wifi-join-error");
      if (error) error.textContent = state.wifi.error;
    }
    return;
  }
  state.wifi.draft = "";
  state.wifi.error = "";
  connectWifi(network);
}

function connectWifi(network) {
  const wifi = state.wifi;
  wifi.joinFor = null;
  wifi.error = "";
  wifi.connecting = network.ssid;
  renderWifi();
  setTimeout(() => {
    if (!state.wifi.on) return;
    state.wifi.connecting = null;
    state.wifi.connected = network.ssid;
    state.wifi.draft = "";
    renderWifi();
    if (state.page === 1) announce(`已连接到 ${network.ssid}`);
  }, 1000 + Math.round(Math.random() * 350));
}

$("wifi-toggle").addEventListener("change", (event) => {
  const wifi = state.wifi;
  wifi.on = event.target.checked;
  wifi.connected = null;
  wifi.connecting = null;
  wifi.joinFor = null;
  wifi.draft = "";
  wifi.error = "";
  renderWifi();
  if (state.page === 1) announce(wifi.on ? "Wi-Fi 已开启，正在搜索网络" : "Wi-Fi 已关闭，可以继续下一步");
});

/* --------------------------------------------------------------- bluetooth */

function btStatusText() {
  const bluetooth = state.bluetooth;
  if (!bluetooth.on) return "蓝牙已关闭";
  if (bluetooth.busy) {
    const device = BT_DEVICES.find((entry) => entry.id === bluetooth.busy);
    const name = device ? device.name : "设备";
    return bluetooth.paired.has(bluetooth.busy) ? `正在断开 ${name}…` : `正在配对 ${name}…`;
  }
  if (bluetooth.scanning) return "正在搜索附近的设备…";
  if (bluetooth.paired.size > 0) return `${bluetooth.paired.size} 台设备已连接`;
  return "没有已连接的设备";
}

function renderBluetooth() {
  const bluetooth = state.bluetooth;
  $("bt-status").textContent = btStatusText();
  $("bt-toggle").checked = bluetooth.on;

  const list = $("bt-list");
  const more = $("bt-more");
  const scrollTop = list.scrollTop;
  list.replaceChildren();
  more.hidden = true;

  if (!bluetooth.on) {
    list.append(emptyRow("蓝牙已关闭，打开开关后会重新搜索设备"));
    return;
  }

  if (bluetooth.scanning) {
    const scanning = emptyRow("正在搜索鼠标、键盘、音箱…");
    scanning.classList.add("scanning");
    list.append(scanning);
    return;
  }

  const priority = BT_DEVICES.filter(device => bluetooth.paired.has(device.id) || device.id === bluetooth.busy);
  const nearby = BT_DEVICES.filter(device => !priority.includes(device));
  const collapsedCount = Math.max(0, 4 - priority.length);
  const extraCount = nearby.length - collapsedCount;
  const devices = priority.concat(bluetooth.expanded ? nearby : nearby.slice(0, collapsedCount));
  more.hidden = extraCount <= 0;
  more.setAttribute("aria-expanded", String(bluetooth.expanded));
  more.textContent = bluetooth.expanded ? "收起设备" : `显示另外 ${extraCount} 台设备`;
  for (const device of devices) {
    const isPaired = bluetooth.paired.has(device.id);
    const isBusy = bluetooth.busy === device.id;

    const item = document.createElement("li");
    item.className = "device-item";
    item.classList.toggle("is-connected", isPaired);
    item.classList.toggle("is-busy", isBusy);

    const row = document.createElement("button");
    row.type = "button";
    row.className = "device-row";
    row.disabled = bluetooth.busy !== null;

    const monogram = document.createElement("span");
    monogram.className = "monogram";
    monogram.setAttribute("aria-hidden", "true");
    monogram.textContent = device.initial;

    const main = document.createElement("span");
    main.className = "device-main";
    const name = document.createElement("span");
    name.className = "device-name";
    name.textContent = device.name;
    const meta = document.createElement("span");
    meta.className = "device-sub";
    meta.textContent = device.type;
    main.append(name, meta);

    const side = document.createElement("span");
    side.className = "device-side";
    if (isBusy) {
      side.innerHTML = '<span class="mini-spin" aria-hidden="true"></span>';
    } else if (isPaired) {
      side.classList.add("chip");
      side.textContent = "已连接";
    } else {
      side.classList.add("chip");
      side.textContent = "配对";
    }

    row.append(monogram, main, side);
    row.setAttribute("aria-label", `${device.name}，${device.type}，${isPaired ? "已连接，点击断开" : "点击配对"}`);
    row.addEventListener("click", () => toggleBluetoothDevice(device));
    item.append(row);
    list.append(item);
  }
  if (!devices.length) list.append(emptyRow("没有发现附近的蓝牙设备"));
  if (bluetooth.expanded) list.scrollTop = scrollTop;
}

$("bt-more").addEventListener("click", () => {
  state.bluetooth.expanded = !state.bluetooth.expanded;
  renderBluetooth();
});

function toggleBluetoothDevice(device) {
  const bluetooth = state.bluetooth;
  if (!bluetooth.on || bluetooth.busy) return;
  const isPaired = bluetooth.paired.has(device.id);
  bluetooth.busy = device.id;
  renderBluetooth();
  const delay = isPaired ? 550 : 1000 + Math.round(Math.random() * 300);
  setTimeout(() => {
    if (!state.bluetooth.on) {
      state.bluetooth.busy = null;
      renderBluetooth();
      return;
    }
    state.bluetooth.busy = null;
    if (isPaired) state.bluetooth.paired.delete(device.id);
    else state.bluetooth.paired.add(device.id);
    renderBluetooth();
    if (state.page === 1) announce(isPaired ? `${device.name} 已断开` : `${device.name} 已配对待用`);
  }, delay);
}

function scanBluetooth() {
  const bluetooth = state.bluetooth;
  if (!bluetooth.on) return;
  bluetooth.scanning = true;
  renderBluetooth();
  setTimeout(() => {
    if (!state.bluetooth.on) return;
    state.bluetooth.scanning = false;
    renderBluetooth();
  }, 900);
}

$("bt-toggle").addEventListener("change", (event) => {
  const bluetooth = state.bluetooth;
  bluetooth.on = event.target.checked;
  bluetooth.busy = null;
  bluetooth.paired.clear();
  if (bluetooth.on) {
    scanBluetooth();
    if (state.page === 1) announce("蓝牙已开启，正在搜索设备");
  } else {
    bluetooth.scanning = false;
    renderBluetooth();
    if (state.page === 1) announce("蓝牙已关闭，可以继续下一步");
  }
});

/* ----------------------------------------------------------------- account */

const accountInputs = ["username", "hostname", "password", "confirm"].map($);
const RESERVED_NAMES = ["root", "daemon", "nobody", "systemd", "_mocha-setup"];

function fail(field, message) {
  for (const input of document.querySelectorAll("input[aria-invalid]")) {
    input.removeAttribute("aria-invalid");
  }
  field.setAttribute("aria-invalid", "true");
  announce(message, "error");
  field.focus({ preventScroll: true });
  requestAnimationFrame(() => {
    field.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
  });
  return false;
}

function validateAccount() {
  const username = $("username").value;
  const hostname = $("hostname").value;
  const password = $("password").value;

  if (!/^[a-z][a-z0-9_-]{0,30}$/.test(username)) {
    return fail($("username"), "用户名须以小写字母开头，最多 31 位");
  }
  if (RESERVED_NAMES.includes(username)) {
    return fail($("username"), "这个用户名已保留，请换一个");
  }
  if (!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(hostname)) {
    return fail($("hostname"), "计算机名称只可使用小写字母、数字和短横线");
  }
  if (password.length < 8 || password.length > 128 || /[\x00-\x1f\x7f]/.test(password)) {
    return fail($("password"), "密码需为 8–128 个字符，不含控制字符");
  }
  if (password !== $("confirm").value) {
    return fail($("confirm"), "两次输入的密码不一致，请再确认一下");
  }
  for (const input of document.querySelectorAll("input[aria-invalid]")) {
    input.removeAttribute("aria-invalid");
  }
  clearFeedback();
  return true;
}

for (const input of accountInputs) {
  input.addEventListener("focus", () => setActiveInput(input));
  input.addEventListener("input", () => {
    input.removeAttribute("aria-invalid");
    clearFeedback();
  });
}

$("show-password").addEventListener("pointerdown", (event) => event.preventDefault());
$("show-password").addEventListener("click", () => {
  const reveal = $("password").type === "password";
  const type = reveal ? "text" : "password";
  $("password").type = type;
  $("confirm").type = type;
  $("show-password").setAttribute("aria-pressed", String(reveal));
  $("show-password").classList.toggle("active", reveal);
});

/* ---------------------------------------------------------------- summary */

function pairedDeviceNames() {
  return BT_DEVICES.filter((device) => state.bluetooth.paired.has(device.id)).map((device) => device.name);
}

function wifiSummary() {
  if (!state.wifi.on) return "已关闭";
  return state.wifi.connected ? state.wifi.connected : "未连接";
}

function bluetoothSummary() {
  if (!state.bluetooth.on) return "已关闭";
  const names = pairedDeviceNames();
  return names.length ? names.join("、") : "未连接";
}

function summaryRows() {
  return [
    { icon: "user", label: "账户", value: $("username").value },
    { icon: "monitor", label: "主机", value: $("hostname").value },
    { icon: "globe", label: "语言", value: $("locale").selectedOptions[0]?.textContent ?? "" },
    { icon: "clock", label: "时区", value: $("timezone").selectedOptions[0]?.textContent ?? "" },
    { icon: "wifi", label: "Wi-Fi", value: wifiSummary() },
    { icon: "bluetooth", label: "蓝牙", value: bluetoothSummary() },
  ];
}

function buildSummary() {
  const list = $("summary");
  list.replaceChildren();
  const svgNS = "http://www.w3.org/2000/svg";
  for (const row of summaryRows()) {
    const term = document.createElement("dt");
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "row-icon");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS(svgNS, "use");
    use.setAttribute("href", `#icon-${row.icon}`);
    svg.append(use);
    const label = document.createElement("span");
    label.textContent = row.label;
    term.append(svg, label);
    const value = document.createElement("dd");
    value.textContent = row.value;
    list.append(term, value);
  }
  $("done-wifi").textContent = wifiSummary();
  const names = pairedDeviceNames();
  $("done-bt").textContent = names.length ? `${names.length} 台设备` : (state.bluetooth.on ? "未连接" : "已关闭");
}

/* ---------------------------------------------------------------- keyboard */

const SYMBOLS = ["-", "_", ".", "@", "#", "$", "%", "&", "!"];

function renderKeyboard() {
  const rows = $("keyboard-rows");
  rows.replaceChildren();

  for (const letters of ["1234567890", "qwertyuiop", "asdfghjkl"]) {
    const row = document.createElement("div");
    row.className = "keyboard-row";
    for (const letter of letters) addKey(row, letter, letter);
    rows.append(row);
  }

  const fourth = document.createElement("div");
  fourth.className = "keyboard-row";
  addKey(fourth, state.shift ? "⇧ 已开启" : "⇧", "shift", `special${state.shift ? " active" : ""}`);
  for (const letter of "zxcvbnm") addKey(fourth, state.shift ? letter.toUpperCase() : letter, letter);
  addKey(fourth, "退格", "backspace", "special");
  rows.append(fourth);

  const fifth = document.createElement("div");
  fifth.className = "keyboard-row";
  SYMBOLS.forEach((symbol, index) => addKey(fifth, symbol, symbol, index >= 3 ? "symbol extra" : "symbol"));
  addKey(fifth, "空格", "space", "space");
  addKey(fifth, "下一项 ↵", "enter", "special enter");
  rows.append(fifth);
}

function addKey(row, label, value, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `key ${className}`.trim();
  button.textContent = label;
  const ariaLabel =
    value === "space" ? "空格" : value === "backspace" ? "退格" : value === "enter" ? "下一项" : value === "shift" ? "Shift" : label;
  button.setAttribute("aria-label", ariaLabel);
  button.addEventListener("click", () => pressKey(value));
  row.append(button);
}

function pressKey(value) {
  if (value === "shift") {
    state.shift = !state.shift;
    renderKeyboard();
    return;
  }
  if (value === "enter") {
    focusNextOrSubmit();
    return;
  }
  insertText(value);
}

function insertText(value) {
  const input = state.activeInput;
  if (!input) return;
  input.focus({ preventScroll: true });
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? start;

  if (value === "backspace") {
    if (start === 0 && end === 0) return;
    let from = start;
    if (start === end) {
      const glyph = [...input.value.slice(0, start)].at(-1);
      from -= glyph ? glyph.length : 0;
    }
    input.setRangeText("", from, end, "end");
  } else {
    const text = value === "space" ? " " : /^[a-z]$/.test(value) && state.shift ? value.toUpperCase() : value;
    const nextLength = input.value.length - (end - start) + text.length;
    if (input.maxLength > 0 && nextLength > input.maxLength) return;
    input.setRangeText(text, start, end, "end");
  }
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function focusNextOrSubmit() {
  if (state.page === 2) {
    const index = accountInputs.indexOf(state.activeInput);
    if (index >= 0 && index < accountInputs.length - 1) {
      accountInputs[index + 1].focus({ preventScroll: true });
    } else if (index === accountInputs.length - 1) {
      $("setup-form").requestSubmit();
    }
    return;
  }

  if (state.page === 1 && state.wifi.joinFor) {
    const network = WIFI_NETWORKS.find((entry) => entry.ssid === state.wifi.joinFor);
    if (network) submitWifiPassword(network);
  }
}

function setKeyboard(open) {
  $("keyboard").hidden = !open;
  $("keyboard-toggle").setAttribute("aria-expanded", String(open));
  document.body.classList.toggle("keyboard-open", open);
  if (open && state.activeInput) {
    requestAnimationFrame(() => {
      state.activeInput?.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    });
  }
}

$("keyboard-toggle").addEventListener("click", () => {
  if (!$("keyboard").hidden) {
    setKeyboard(false);
    return;
  }

  if (!state.activeInput) {
    if (state.page === 2) {
      $("username").focus({ preventScroll: true });
    } else if (state.page === 1) {
      const network =
        WIFI_NETWORKS.find((entry) => entry.secured && entry.ssid !== state.wifi.connected) ?? WIFI_NETWORKS[0];
      chooseWifi(network);
    }
  }

  setKeyboard(true);
  requestAnimationFrame(() => {
    if (state.activeInput) {
      state.activeInput.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    }
  });
});

$("hide-keyboard").addEventListener("click", () => setKeyboard(false));

$("keyboard").addEventListener("pointerdown", (event) => {
  if (event.target.closest(".key")) event.preventDefault();
});

// Focus leaving the input for a normal control should not leave the on-screen
// keyboard aimed at a field the user can no longer see.
document.addEventListener("focusin", (event) => {
  const target = event.target;
  if (!(target instanceof Element) || target.matches("input")) return;
  if (target.closest("#keyboard") || target.closest(".eye") || target === $("keyboard-toggle")) return;
  if (!state.activeInput) return;
  state.activeInput = null;
  if (!$("keyboard").hidden) setKeyboard(false);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("keyboard").hidden) setKeyboard(false);
});

/* ------------------------------------------------------------ page machine */

function showPage(next, focus = true) {
  state.page = next;
  state.activeInput = null;

  pages.forEach((section, index) => {
    const isActive = index === next;
    section.hidden = !isActive;
    section.classList.toggle("active", isActive);
    section.classList.remove("enter");
  });

  const section = pages[next];
  if (!section) return;
  void section.offsetWidth;
  section.classList.add("enter");

  $("step-label").textContent = TITLES[next] ?? "";
  const stepIndex = Math.min(next, 4);
  [...$("progress-dots").children].forEach((dot, index) => {
    dot.classList.toggle("current", stepIndex < 4 && index === stepIndex);
    dot.classList.toggle("completed", index < stepIndex);
  });

  $("actions").hidden = next >= 4;
  $("back").hidden = next >= 4;
  $("back").disabled = next === 0;
  $("next").disabled = next >= 4;
  $("next").innerHTML = `${NEXT_LABELS[next] ?? ""}${
    next < 4 ? '<span class="arrow" aria-hidden="true">→</span>' : ""
  }`;
  $("keyboard-toggle").hidden = next !== 1 && next !== 2;
  if (next !== 1 && next !== 2) setKeyboard(false);

  pageStage.scrollTop = 0;
  closeChoices();
  clearFeedback();

  if (!focus) return;
  requestAnimationFrame(() => {
    if (next === 2) {
      $("username").focus({ preventScroll: true });
    } else if (next === 1) {
      const wifiInput = $("wifi-password");
      if (wifiInput) {
        wifiInput.focus({ preventScroll: true });
      } else {
        if (!$("keyboard").hidden) setKeyboard(false);
        section.querySelector("h1")?.focus({ preventScroll: true });
      }
    } else {
      section.querySelector("h1")?.focus({ preventScroll: true });
    }
  });
}

$("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.page === 0) {
    showPage(1);
  } else if (state.page === 1) {
    showPage(2);
  } else if (state.page === 2) {
    if (validateAccount()) {
      buildSummary();
      showPage(3);
    }
  } else if (state.page === 3) {
    startApply();
  }
});

$("back").addEventListener("click", () => {
  if (state.page > 0 && state.page < 4) showPage(state.page - 1);
});

/* --------------------------------------------------------------- applying */

function startApply() {
  if (applying) return;
  applying = true;
  buildSummary();
  showPage(4);
  $("loading-status").textContent = "正在准备你的桌面";
  setTimeout(finishApply, 2400);
}

function finishApply() {
  $("password").value = "";
  $("confirm").value = "";
  $("password").type = "password";
  $("confirm").type = "password";
  $("show-password").classList.remove("active");
  $("show-password").setAttribute("aria-pressed", "false");
  const wifiInput = $("wifi-password");
  if (wifiInput) wifiInput.value = "";
  state.wifi.draft = "";
  state.activeInput = null;
  applying = false;
  showPage(5);
}

/* -------------------------------------------------------------------- boot */

setupChoices();
renderWifi();
renderBluetooth();
renderKeyboard();
showPage(0, false);

setTimeout(() => {
  if (!state.bluetooth.on) return;
  state.bluetooth.scanning = false;
  renderBluetooth();
}, 1100);

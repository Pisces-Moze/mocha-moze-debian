/* Native actions only. Appearance remains in the approved index/style/app. */
"use strict";
let refreshTimer = 0;
let refreshPending = false;
let pageEpoch = 0;
let nativePairingRow = null;

function clearNativePairingRow() {
  if (!nativePairingRow) return;
  nativePairingRow.querySelectorAll("button").forEach(button => { button.disabled = true; });
  nativePairingRow.remove();
  nativePairingRow = null;
}

function nativePage(page) {
  clearTimeout(refreshTimer);
  pageEpoch += 1;
  if (page === 1) {
    MochaNative.call("start-scan", {}).then(nativeRefresh).catch(() => announce("无法开启设备搜索。", "error"));
  } else MochaNative.call("stop-scan", {}).catch(() => {});
}

async function nativeRefresh() {
  if (refreshPending || state.page !== 1) return;
  if (state.wifi.connecting || state.bluetooth.busy) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(nativeRefresh, 6000);
    return;
  }
  clearTimeout(refreshTimer);
  const epoch = pageEpoch;
  refreshPending = true;
  try {
    const data = await MochaNative.call("networks", {});
    if (epoch !== pageEpoch || state.page !== 1) return;
    const wifiChanged = state.wifi.on !== data.wifi.on ||
      state.wifi.available !== data.wifi.available ||
      state.wifi.connected !== data.wifi.connected ||
      JSON.stringify(WIFI_NETWORKS) !== JSON.stringify(data.wifi.networks);
    const btChanged = state.bluetooth.on !== data.bluetooth.on || state.bluetooth.scanning ||
      JSON.stringify(BT_DEVICES) !== JSON.stringify(data.bluetooth.devices);
    WIFI_NETWORKS.splice(0, WIFI_NETWORKS.length, ...data.wifi.networks);
    BT_DEVICES.splice(0, BT_DEVICES.length, ...data.bluetooth.devices);
    state.wifi.on = data.wifi.on;
    state.wifi.available = data.wifi.available;
    state.wifi.connected = data.wifi.connected;
    state.bluetooth.on = data.bluetooth.on;
    state.bluetooth.scanning = false;
    state.bluetooth.paired = new Set(data.bluetooth.devices.filter(d => d.connected).map(d => d.id));
    // Updating lists during typing destroys focus/selection, so defer that list.
    if (wifiChanged && !state.wifi.joinFor && !state.wifi.connecting) renderWifi();
    if (btChanged && !state.bluetooth.busy) renderBluetooth();
  } catch (_) {
    if (epoch === pageEpoch) announce("无法读取连接状态，可以稍后在系统设置中连接。", "error");
  } finally {
    refreshPending = false;
    if (state.page === 1) refreshTimer = setTimeout(nativeRefresh, 6000);
  }
}

async function nativeRadio(radio, on) {
  try {
    await MochaNative.call("radio", {radio, on});
    state.wifi.joinFor = null;
    state.wifi.draft = "";
    await nativeRefresh();
    renderWifi(); renderBluetooth();
  } catch (_) {
    $(radio === "wifi" ? "wifi-toggle" : "bt-toggle").checked = !on;
    announce("无法切换无线设备，请稍后重试。", "error");
  }
}

async function nativeConnectWifi(network, password = "") {
  if (state.wifi.connecting) return;
  state.wifi.connecting = network.ssid;
  state.wifi.joinFor = null;
  state.wifi.draft = "";
  setKeyboard(false);
  renderWifi();
  try {
    await MochaNative.call("wifi-connect", {ssid: network.ssid, password});
    password = "";
    state.wifi.connected = network.ssid;
    announce(`已连接到 ${network.ssid}`);
  } catch (_) {
    state.wifi.joinFor = network.secured ? network.ssid : null;
    state.wifi.error = "连接未成功，请检查密码与信号后重试。";
    announce(state.wifi.error, "error");
  } finally {
    password = "";
    state.wifi.connecting = null;
    renderWifi();
  }
}

async function nativeBluetooth(device) {
  if (state.bluetooth.busy) return;
  state.bluetooth.busy = device.id;
  renderBluetooth();
  try {
    await MochaNative.call("bluetooth-connect", {id: device.id, disconnect: !!device.connected});
    announce(device.connected ? "设备已断开" : "设备已连接");
  } catch (_) {
    announce("配对或连接未成功，请让设备重新进入配对模式。", "error");
  } finally {
    state.bluetooth.busy = null;
    await nativeRefresh();
    renderBluetooth();
  }
}

window.mochaPairing = (message) => {
  // Native BlueZ DisplayPasskey/DisplayPinCode. Cleared on completion/cancel.
  announce(message);
};

window.addEventListener("mocha-native-event", event => {
  const {event: kind, data} = event.detail;
  if (kind === "pairing-clear") { clearNativePairingRow(); return announce(""); }
  if (kind === "pairing-code") return announce(`请在蓝牙键盘输入 ${data.code}，然后按 Enter`);
  if (kind !== "pairing-request") return;
  clearNativePairingRow();
  const needsInput = ["RequestPinCode", "RequestPasskey"].includes(data.method);
  announce(needsInput ? "输入设备的配对码" : `确认与所选设备配对${data.code ? `：${data.code}` : ""}`);
  const row = document.createElement("div");
  nativePairingRow = row;
  row.className = "wifi-join-row";
  let input;
  if (needsInput) {
    input = document.createElement("input"); input.type = "text";
    input.maxLength = data.method === "RequestPasskey" ? 6 : 16;
    input.setAttribute("aria-label", "配对码");
    input.addEventListener("focus", () => setActiveInput(input));
    row.append(input);
  }
  for (const [label, accepted] of [["取消", false], ["确认", true]]) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "mini-primary"; button.textContent = label;
    button.onclick = () => {
      const value = accepted ? (needsInput ? input.value : true) : false;
      row.querySelectorAll("button").forEach(item => { item.disabled = true; });
      MochaNative.call("pairing-reply", {token: data.token, value}).catch(() => {
        if (nativePairingRow === row) announce("配对请求已结束，请重新选择设备。", "error");
      }).finally(() => {
        if (nativePairingRow === row) clearNativePairingRow();
      });
    };
    row.append(button);
  }
  $("feedback").append(row);
});

async function nativeApply() {
  try {
    await MochaNative.call("apply", {
      username: $("username").value, hostname: $("hostname").value,
      password: $("password").value, locale: $("locale").value,
      timezone: $("timezone").value,
    });
    // Queued is not committed. Keep the existing loading page until the root
    // service hands over to the desktop, or reopens setup after a failure.
    $("password").value = "";
    $("confirm").value = "";
    $("loading-status").textContent = "正在应用设置并启动桌面";
    nativeReleaseMedia();
  } catch (_) {
    // The request may have reached root before the bridge/socket failed.
    // Ask the read-only status instead of reopening a possible parallel submit.
    $("loading-status").textContent = "正在确认设置状态，请稍候";
    const status = await nativeRestoreSetup();
    // The backend stops listening once accepted. A live status response with
    // no transaction is therefore a definite pre-queue rejection, not a lost
    // acknowledgement. Let the user correct the form in that one case.
    if (status && status.phase === "new") {
      applying = false;
      $("password").value = "";
      $("confirm").value = "";
      showPage(2);
      announce("设置未受理，请检查账户资料并重新输入密码。", "error");
    }
  }
}

function nativeSleep(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function nativeSetupStatus() {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      return await MochaNative.call("setup-status", {});
    } catch (_) {
      if (attempt === 3) throw new Error("setup-status unavailable");
      await nativeSleep(200 * attempt);
    }
  }
  throw new Error("setup-status unavailable");
}

async function nativeRestoreSetup() {
  let result;
  try {
    result = await nativeSetupStatus();
  } catch (_) {
    announce("无法读取设置恢复状态：后端暂不可用，请稍候重试或重启。", "error");
    return;
  }
  if (!result || !result.retry) return result;
  const choices = result.choices || {};
  // Restore non-secret fields only; password fields are always cleared below.
  for (const id of ["username", "hostname"]) {
    if (typeof choices[id] === "string") $(id).value = choices[id];
  }
  const unresolved = [];
  for (const id of ["locale", "timezone"]) {
    if (typeof choices[id] !== "string") {
      unresolved.push(id);
      continue;
    }
    const widget = choiceWidgets.find(item => item.select.id === id);
    const option = widget && [...widget.menu.querySelectorAll(".choice-option")]
      .find(item => item.dataset.value === choices[id]);
    if (!option) {
      unresolved.push(id);
      continue;
    }
    option.click();
    if (widget.select.value !== choices[id]) unresolved.push(id);
  }
  $("password").value = "";
  $("confirm").value = "";
  applying = false;
  showPage(2);
  announce(unresolved.length
    ? "部分设置无法恢复，请重新选择语言和时区后继续。"
    : (result.error || "设置未完成，请重新确认并输入密码。"), "error");
  return result;
}

function nativeReleaseMedia() {
  clearTimeout(refreshTimer);
  window.mochaSuspended = true;
  const video = $("bg-video");
  if (!video) return;
  if (typeof video.pause === "function") video.pause();
  video.removeAttribute("src");
  video.querySelectorAll("source").forEach(source => source.removeAttribute("src"));
  if (typeof video.load === "function") video.load();
}
window.addEventListener("pagehide", nativeReleaseMedia, {once: true});
window.addEventListener("mocha-visibility", event => {
  window.mochaSuspended = !event.detail;
  const video = $("bg-video");
  if (!video) return;
  if (!event.detail && typeof video.pause === "function") video.pause();
  else if (!reduceMotion && typeof video.play === "function") video.play().catch(() => {});
});
// Freeze CSS animations as well as canvas/video while the native surface is hidden.
const pauseStyle = document.createElement("style");
pauseStyle.textContent = "html.mocha-hidden *,html.mocha-hidden *::before,html.mocha-hidden *::after{animation-play-state:paused!important}";
document.head.append(pauseStyle);
window.addEventListener("mocha-visibility", event => document.documentElement.classList.toggle("mocha-hidden", !event.detail));

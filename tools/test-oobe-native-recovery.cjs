#!/usr/bin/env node
"use strict";

// Offline DOM/MochaNative mocks for oobe/native.js recovery behavior.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "..", "oobe", "native.js"), "utf8");

function makeElement(id) {
  return {
    id, value: "", textContent: "", type: "password", hidden: false, dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    style: {}, append() {}, remove() {}, setAttribute() {}, getAttribute() { return ""; },
    focus() {}, addEventListener() {}, pause() {}, removeAttribute() {}, load() {},
    querySelectorAll() { return []; },
  };
}

function makeChoice(id, values, selected) {
  const select = { id, value: selected ?? values[0] };
  const options = values.map(value => ({
    dataset: { value },
    click() { select.value = value; },
  }));
  return {
    select,
    trigger: { setAttribute() {}, focus() {} },
    menu: { hidden: true, querySelectorAll() { return options; } },
  };
}

function makeContext({ status, apply }) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, makeElement(id));
    return elements.get(id);
  };
  const announcements = [];
  const calls = [];
  const context = {
    page: 0, applying: false, finishedApply: false,
    choiceWidgets: [
      makeChoice("locale", ["zh_CN.UTF-8", "en_US.UTF-8"], "zh_CN.UTF-8"),
      makeChoice("timezone", ["Asia/Shanghai", "UTC"], "Asia/Shanghai"),
    ],
    state: { page: 0, activeInput: null },
    reduceMotion: false,
    setTimeout, clearTimeout,
    $: element,
    announce(message, tone) { announcements.push({ message, tone }); },
    showPage(next) { context.page = next; },
    finishApply() { context.finishedApply = true; },
    MochaNative: {
      async call(action, data) {
        calls.push({ action, data });
        if (action === "setup-status") return status(calls);
        if (action === "apply") return apply(calls);
        return {};
      },
    },
    window: { addEventListener() {}, mochaSuspended: false },
    document: {
      getElementById: element,
      createElement() { return makeElement("created"); },
      addEventListener() {},
      head: { append() {} },
      documentElement: { classList: { toggle() {} } },
      querySelectorAll() { return []; },
    },
    Element: function Element() {},
  };
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(source + "\n;globalThis.__nativeApply = nativeApply; globalThis.__nativeRestoreSetup = nativeRestoreSetup;", context,
    { filename: "native.js" });
  return { context, elements, announcements, calls, element };
}

async function testTransientStartupRecovers() {
  let setupStatusCalls = 0;
  const harness = makeContext({
    status() { setupStatusCalls += 1; if (setupStatusCalls === 1) throw new Error("transient"); return {
      retry: true, error: "首次设置未完成",
      choices: { username: "alice", hostname: "mochadev", locale: "zh_CN.UTF-8", timezone: "Asia/Shanghai" },
    }; },
    apply() { return {}; },
  });
  await harness.context.__nativeRestoreSetup();
  assert.strictEqual(setupStatusCalls, 2, "startup status must retry once");
  assert.strictEqual(harness.context.page, 2, "restore must reopen account page");
  assert.strictEqual(harness.element("username").value, "alice");
  assert.strictEqual(harness.element("hostname").value, "mochadev");
  assert.strictEqual(harness.element("password").value, "");
  assert.strictEqual(harness.element("confirm").value, "");
  assert.ok(harness.announcements.some(item => item.message.includes("首次设置未完成")));
}

async function testMissingChoicePromptsReselect() {
  const harness = makeContext({
    status() { return { retry: true, choices: {
      username: "alice", hostname: "mochadev", locale: "fr_FR.UTF-8", timezone: "Asia/Shanghai" } }; },
    apply() { return {}; },
  });
  await harness.context.__nativeRestoreSetup();
  assert.strictEqual(harness.context.page, 2);
  assert.ok(harness.announcements.some(item => item.message.includes("重新选择")));
  assert.strictEqual(harness.context.choiceWidgets[0].select.value, "zh_CN.UTF-8");
}

async function testQueuedKeepsLoadingWithoutFinishApply() {
  const harness = makeContext({ status() { return { retry: false }; }, apply() { return {}; } });
  harness.context.applying = true;
  harness.context.page = 4;
  harness.element("username").value = "alice";
  harness.element("password").value = "secret-password";
  harness.element("confirm").value = "secret-password";
  await harness.context.__nativeApply();
  assert.strictEqual(harness.context.finishedApply, false, "queued must not finishApply");
  assert.strictEqual(harness.context.page, 4, "queued must stay on loading page");
  assert.ok(harness.element("loading-status").textContent.includes("正在应用设置"));
  assert.strictEqual(harness.element("password").value, "");
  assert.strictEqual(harness.element("confirm").value, "");
}

async function testAmbiguousSubmitDoesNotReopenForm() {
  const harness = makeContext({
    status() { return { retry: false }; },
    apply() { throw new Error("socket interrupted"); },
  });
  harness.context.applying = true;
  harness.context.page = 4;
  await harness.context.__nativeApply();
  assert.strictEqual(harness.context.page, 4, "ambiguous submit must keep loading");
  assert.strictEqual(harness.context.applying, true, "ambiguous submit must not allow parallel submit");
  assert.strictEqual(harness.context.finishedApply, false);
  assert.ok(harness.element("loading-status").textContent.includes("确认设置状态"));
}

async function testDefiniteRejectionCanBeCorrected() {
  const harness = makeContext({
    status() { return {phase: "new", retry: false}; },
    apply() { throw new Error("backend rejected invalid reserved account"); },
  });
  harness.context.applying = true;
  harness.context.page = 4;
  await harness.context.__nativeApply();
  assert.strictEqual(harness.context.page, 2);
  assert.strictEqual(harness.context.applying, false);
  assert.strictEqual(harness.element("password").value, "");
  assert.strictEqual(harness.context.finishedApply, false);
}

(async () => {
  // WebKit media=false can expose <video> without HTMLMediaElement methods.
  // The form hook must still complete so the subsequent IPC boot can run.
  const formBuilder = require("fs").readFileSync(require("path").join(__dirname, "../oobe/build-form-web.py"), "utf8");
  const hook = formBuilder.match(/NATIVE_INTRO = '''([\s\S]*?)'''/)[1];
  let removed = false;
  const background = {removeAttribute() {}, querySelectorAll() {return [];}, remove() {removed = true;}};
  const hookContext = {window: {}, document: {
    getElementById(id) {return id === "bg-video" ? background : null;},
    querySelector() {return null;}, body: {classList: {remove() {}}},
    documentElement: {dataset: {}},
  }};
  vm.runInNewContext(hook, hookContext);
  assert.strictEqual(hookContext.window.startMochaIntro(), true);
  assert.strictEqual(removed, true);
  await testTransientStartupRecovers();
  await testMissingChoicePromptsReselect();
  await testQueuedKeepsLoadingWithoutFinishApply();
  await testAmbiguousSubmitDoesNotReopenForm();
  await testDefiniteRejectionCanBeCorrected();
  console.log("oobe native recovery tests: OK");
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});

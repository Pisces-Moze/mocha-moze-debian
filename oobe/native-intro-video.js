/* Pre-rendered approved artwork. No particle canvas or per-frame DOM layout. */
"use strict";
window.startMochaIntro = reducedMotion => {
  const intro = document.getElementById("intro");
  const stage = document.querySelector(".stage");
  if (!intro) return true;
  if (reducedMotion) {intro.remove(); return true;}
  const asset = window.MochaIntroAsset;
  if (!asset) return false;
  document.getElementById("intro-canvas")?.remove();
  document.getElementById("intro-greetings")?.remove();
  intro.style.backdropFilter = "none";
  intro.style.webkitBackdropFilter = "none";
  const enter = document.getElementById("intro-enter");
  const background = document.getElementById("bg-video");
  const backgroundSources = [...background.querySelectorAll("source")].map(source => [source, source.getAttribute("src")]);
  background.pause(); background.autoplay = false; background.preload = "none";
  background.removeAttribute("autoplay"); background.removeAttribute("src");
  backgroundSources.forEach(([source]) => source.removeAttribute("src"));
  background.poster = asset.backgroundPoster;
  background.load();
  const video = document.createElement("video");
  video.muted = video.defaultMuted = true; video.playsInline = true;
  video.setAttribute("muted", ""); video.setAttribute("playsinline", "");
  video.setAttribute("aria-hidden", "true"); video.tabIndex = -1;
  video.preload = "auto"; video.poster = asset.initialPoster; video.src = asset.file;
  video.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:fill;z-index:1;pointer-events:none";
  intro.prepend(video);
  window.mochaIntroRenderer = "pre-rendered-vde";
  window.mochaIntroVideo = video;
  let phase = "idle", frameCallback = 0;
  function positionButton() {
    const width = innerWidth, height = innerHeight;
    const radius = Math.min(width, height) * (width < 620 ? 0.28 : 0.22);
    if (enter) enter.style.top = `${Math.min(height * 0.55 + radius + (width < 620 ? 78 : 92), height - 72)}px`;
  }
  function seekLoop() {
    if (phase === "idle" && !video.seeking && video.readyState > 0 && video.currentTime >= asset.loopEnd - 1 / asset.fps) {
      video.currentTime = asset.loopStart;
    }
  }
  function videoFrame() {
    if (phase !== "idle") return;
    seekLoop();
    frameCallback = video.requestVideoFrameCallback(videoFrame);
  }
  video.addEventListener("timeupdate", seekLoop);
  video.addEventListener("ended", () => {
    if (phase === "idle") {video.currentTime = asset.loopStart; video.play().catch(() => {});}
  });
  video.addEventListener("error", () => {
    window.mochaIntroVideoError = video.error?.code ?? -1;
    video.poster = asset.poster;
    video.pause(); video.removeAttribute("src"); video.load();
    // Retain the exported poster and working button if a decoder is unavailable.
  }, {once: true});
  function visibility() {
    if (phase === "closed") return;
    if (document.hidden || window.mochaSuspended) video.pause();
    else video.play().catch(() => {});
  }
  function restoreBackground(time) {
    document.body.classList.remove("no-video");
    background.preload = "auto";
    backgroundSources.forEach(([source, src]) => {if (src) source.setAttribute("src", src);});
    background.addEventListener("loadedmetadata", () => {
      if (Number.isFinite(background.duration) && background.duration > 0) background.currentTime = time % background.duration;
    }, {once: true});
    background.load(); background.play().catch(() => {});
  }
  function cleanup() {
    if (phase === "closed") return;
    phase = "closed";
    if (frameCallback && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(frameCallback);
    video.pause(); video.removeAttribute("src"); video.load(); video.remove();
    window.mochaIntroVideo = null;
    document.removeEventListener("visibilitychange", visibility);
    window.removeEventListener("mocha-visibility", visibility);
    window.removeEventListener("resize", positionButton);
  }
  function leave() {
    if (phase !== "idle") return;
    phase = "exit"; intro.classList.add("leaving");
    if (frameCallback && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(frameCallback);
    document.body.classList.remove("no-video");
    try {video.currentTime = asset.exitStart; video.play().catch(() => {});} catch (_) {}
    setTimeout(() => {
      intro.classList.add("hide"); stage?.classList.remove("intro-active"); stage?.classList.add("setup-enter");
    }, 500);
    setTimeout(() => {
      // Stop the welcome decoder first. A matching still fills the handoff,
      // avoiding two simultaneous full-size VDE streams during the transition.
      cleanup(); restoreBackground(asset.exitStart); intro.remove();
      document.querySelector(".page:not([hidden]) h1")?.focus({preventScroll: true});
    }, asset.exitDuration * 1000);
  }
  enter?.addEventListener("click", leave);
  window.addEventListener("resize", positionButton);
  window.addEventListener("pagehide", cleanup, {once: true});
  window.addEventListener("mocha-visibility", visibility);
  document.addEventListener("visibilitychange", visibility);
  stage?.classList.add("intro-active"); positionButton();
  if (video.requestVideoFrameCallback) frameCallback = video.requestVideoFrameCallback(videoFrame);
  video.play().catch(() => {});
  return true;
};

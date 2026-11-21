#!/usr/bin/env node
// SPDX-License-Identifier: GPL-2.0-only
// Offline artwork export only. Node/Edge/FFmpeg are never installed on Mocha.
import fs from "node:fs/promises";
import path from "node:path";
import {pathToFileURL} from "node:url";
import {createRequire} from "node:module";
import {spawn} from "node:child_process";
import {once} from "node:events";
import crypto from "node:crypto";

const config = JSON.parse(await fs.readFile(process.argv[2], "utf8"));
const require = createRequire(import.meta.url);
const {chromium} = require(config.playwrightModule || "playwright-core");
const fps = 30, mainEnd = 18, exitDuration = 1.5, frameCount = 585;
const output = path.resolve(config.output);
await fs.mkdir(output, {recursive: false});
const work = path.join(output, "intro-lossless.mkv");
const result = path.join(output, "intro-landscape.mp4");
const filter = [
  "[0:v]fps=30,scale=2816:1584:flags=lanczos:in_color_matrix=bt709,crop=2048:1536,format=rgb24",
  // CSS brightness(.86), saturation(.96), then intro backdrop saturation(1.05).
  "colorchannelmixer=rr=0.86541456:rg=-0.0049192:rb=-0.00049536:gr=-0.00146544:gg=0.8619608:gb=-0.00049536:br=-0.00146544:bg=-0.0049192:bb=0.86638464",
  "gblur=sigma=78:steps=3,format=rgba[background];",
  "[background][1:v]overlay=shortest=1:format=auto,scale=1920:1080:flags=lanczos,format=yuv444p[video]",
].join(",").replace(",[background]", "[background]").replace(";,", ";");
const encode = spawn(config.ffmpeg, [
  "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
  "-thread_queue_size", "8", "-i", path.resolve(config.background),
  "-thread_queue_size", "2", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "png", "-i", "pipe:0",
  "-filter_complex_threads", "2", "-filter_complex", filter,
  "-map", "[video]", "-an", "-frames:v", String(frameCount),
  "-c:v", "ffv1", "-level", "3", "-threads", "4", "-pix_fmt", "yuv444p", work,
], {stdio: ["pipe", "ignore", "inherit"]});
const encoded = new Promise((resolve, reject) => {
  encode.once("error", reject);
  encode.once("close", code => code === 0 ? resolve() : reject(new Error(`FFmpeg export failed: ${code}`)));
});
// Attach an early handler as well as awaiting below: a failed encoder must not
// silently leave the renderer filling an undrained pipe.
let encodeError;
encoded.catch(error => { encodeError = error; });
const browser = await chromium.launch({executablePath: config.browser, headless: true});
try {
  const context = await browser.newContext({viewport: {width: 1365, height: 1024}, deviceScaleFactor: 1.5, reducedMotion: "no-preference"});
  await context.addInitScript(() => {
    let now = 0, sequence = 0, random = 0x4d6f6368;
    const frames = new Map(), timers = new Map();
    Object.defineProperty(performance, "now", {value: () => now});
    Math.random = () => ((random = (Math.imul(random, 1664525) + 1013904223) >>> 0) / 4294967296);
    window.requestAnimationFrame = callback => {const id = ++sequence; frames.set(id, callback); return id;};
    window.cancelAnimationFrame = id => frames.delete(id);
    window.setTimeout = (callback, delay = 0, ...args) => {
      const id = ++sequence; timers.set(id, {callback: () => callback(...args), at: now + Number(delay)}); return id;
    };
    window.clearTimeout = id => timers.delete(id);
    window.exportIntroFrame = (ms, leave) => {
      now = ms;
      if (leave) document.getElementById("intro-enter").click();
      for (const [id, timer] of [...timers]) {
        if (timer.at <= now) {timers.delete(id); timer.callback();}
      }
      const pending = [...frames.values()]; frames.clear();
      pending.forEach(callback => callback(now));
    };
    document.addEventListener("DOMContentLoaded", () => {
      const video = document.getElementById("bg-video");
      video.pause(); video.removeAttribute("autoplay");
      video.querySelectorAll("source").forEach(source => source.removeAttribute("src")); video.load();
    }, {once: true});
  });
  const page = await context.newPage();
  await page.route(/^https?:/, route => route.abort());
  await page.goto(pathToFileURL(path.resolve(config.html)).href, {waitUntil: "load"});
  await page.addStyleTag({content: `
    html,body,.stage{background:transparent!important}
    .bg-video,.topbar,.card,.veil,.intro-enter{visibility:hidden!important}
    .intro,.intro.hide{background:transparent!important;opacity:1!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important}
  `});
  await page.evaluate(() => document.fonts.ready);
  for (let frame = 0; frame < frameCount; frame += 1) {
    if (encodeError) throw encodeError;
    await page.evaluate(({ms, leave}) => window.exportIntroFrame(ms, leave), {ms: frame / fps * 1000, leave: frame === mainEnd * fps});
    const png = await page.screenshot({type: "png", omitBackground: true, animations: "allow", timeout: 30000});
    if (frame === 0 && (png.readUInt32BE(16) !== 2048 || png.readUInt32BE(20) !== 1536)) throw new Error("Unexpected raster size");
    if (!encode.stdin.write(png)) await once(encode.stdin, "drain");
    if (frame % 30 === 0) console.log(JSON.stringify({phase: "artwork", frame, total: frameCount}));
  }
  encode.stdin.end(); await encoded;
  await context.close();
} catch (error) {
  encode.kill(); throw error;
} finally { await browser.close(); }

// A one-second baked dissolve closes the idle loop. Both loop and exit start
// on exact GOP boundaries, so the tablet can seek without decoding a long GOP.
const finish = spawn(config.ffmpeg, [
  "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
  "-i", work, "-ss", "2", "-t", "1", "-i", work, "-ss", "18", "-t", "1.5", "-i", work,
  "-filter_complex_threads", "2", "-filter_complex",
  "[0:v]trim=duration=18,settb=1/30,setpts=N,fps=30[a];[1:v]settb=1/30,setpts=N,fps=30[b];[a][b]xfade=transition=fade:duration=1:offset=17[loop];[2:v]settb=1/30,setpts=N,fps=30[exit];[loop][exit]concat=n=2:v=1:a=0,fps=30,format=yuv420p[video]",
  "-map", "[video]", "-an", "-frames:v", String(frameCount), "-c:v", "libx264", "-profile:v", "baseline", "-level:v", "4.0",
  "-preset", "slow", "-crf", "16", "-threads", "4", "-refs", "1", "-bf", "0", "-g", "30", "-keyint_min", "30",
  "-x264-params", "cabac=0:weightp=0:8x8dct=0:scenecut=0", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
  "-movflags", "+faststart", result,
], {stdio: ["ignore", "ignore", "inherit"]});
const [code] = await once(finish, "close");
if (code !== 0) throw new Error(`Final encoding failed: ${code}`);
const poster = spawn(config.ffmpeg, ["-hide_banner", "-loglevel", "warning", "-nostdin", "-y", "-ss", "3", "-i", result, "-vf", "scale=2048:1536:flags=lanczos,setsar=1", "-frames:v", "1", path.join(output, "intro-landscape.png")], {stdio: ["ignore", "ignore", "inherit"]});
const [posterCode] = await once(poster, "close");
if (posterCode !== 0) throw new Error("Poster export failed");
for (const [input, seek, filter, name] of [
  [result, "0", "scale=2048:1536:flags=lanczos,setsar=1", "intro-start.png"],
  [path.resolve(config.background), "18", "scale=1920:1080:flags=lanczos,setsar=1", "background-poster.jpg"],
]) {
  const child=spawn(config.ffmpeg,["-hide_banner","-loglevel","warning","-nostdin","-y","-ss",seek,"-i",input,"-vf",filter,"-frames:v","1","-update","1","-q:v","2",path.join(output,name)],{stdio:["ignore","ignore","inherit"]});
  const [status]=await once(child,"close");
  if(status!==0)throw new Error("Handoff poster export failed");
}
const hash = crypto.createHash("sha256").update(await fs.readFile(result)).digest("hex");
await fs.writeFile(path.join(output, "intro.json"), JSON.stringify({schema: 1, file: "intro-landscape.mp4", poster: "intro-landscape.png", codedWidth: 1920, codedHeight: 1080, displayWidth: 2048, displayHeight: 1536, fps, loopStart: 3, loopEnd: mainEnd, exitStart: mainEnd, exitDuration, sha256: hash, rendering: "approved-preview-offline", videoFit: "fill"}, null, 2) + "\n");
console.log(JSON.stringify({phase: "complete", file: result, sha256: hash}));

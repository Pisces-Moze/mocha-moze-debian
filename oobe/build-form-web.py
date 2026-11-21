#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the form-phase web tree from the approved native OOBE web output.

The native welcome screen already played the approved animation, so the form
phase must start on the first settings page. Four changes are made to the tree
produced by build-web.py:

1. native-intro.js is replaced by a hook that removes the intro overlay,
   reveals the setup stage immediately, and detaches the background video (no
   WebKit video, no canvas).
2. style.css gets a static-backdrop form phase: the animated background video
   is hidden, live backdrop-filter is removed (with a static backdrop it makes
   WebKit render the form black on Mocha, and it costs a full frame recompute
   whenever anything animates), and the cards use near-opaque fills.
3. index.html no longer autoplays or preloads the 1920x1080 background clip.
   The approved page starts `assets/background.mp4` with `autoplay` and
   `preload="auto"`, and native.js re-plays it on the shell's map event even
   though the form-phase CSS keeps the element hidden. That work (23.5 MB
   media pipeline startup, first-frame decode, media process) is invisible to
   the user and is removed here; the approved artwork tree is unchanged.
4. The intro video/poster assets are pruned from the form tree. They are only
   used by the native intro renderer, which the form phase never starts, and
   the generated tree is checked so nothing can still fetch them.

Measured on Mocha (previous handoff): WebKit idle ~0.01-0.02 core on the form
page. The remaining first-load burst (~0.9 core for 5-10 s) has not been
attributed conclusively; see artifacts/reports/oobe-form-performance-harness-
20261101.md for the source evidence, the changes below and the device-side
measurements required to confirm them.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

MARKER = '/* mocha native form phase */'
FORM_PHASE_VERSION = 3

NATIVE_INTRO = '''/* Form-phase hook: the native welcome screen already played. */
"use strict";
window.startMochaIntro = () => {
  const intro = document.getElementById("intro");
  if (intro) intro.remove();
  const stage = document.querySelector(".stage");
  if (stage) { stage.classList.remove("intro-active"); stage.classList.add("setup-enter"); }
  document.body.classList.remove("no-video");
  const bg = document.getElementById("bg-video");
  if (bg && bg.dataset?.formMotion === undefined) {
    // With media disabled WebKit can expose a plain HTMLElement for <video>.
    // The hidden background must never abort setup before native IPC starts.
    if (typeof bg.pause === "function") bg.pause();
    bg.removeAttribute("autoplay");
    bg.preload = "none";
    bg.removeAttribute("src");
    for (const source of bg.querySelectorAll("source")) source.remove();
    bg.remove();
  }
  document.documentElement.dataset.mochaFormPhase = "1";
  window.mochaIntroRenderer = "native-welcome";
  return true;
};
'''

FORM_CSS = MARKER + '''
.bg-video { display: none !important; }
.stage {
  background:
    radial-gradient(90% 70% at 18% 8%, rgba(46, 96, 128, 0.55), transparent 62%),
    radial-gradient(80% 65% at 86% 18%, rgba(96, 70, 120, 0.42), transparent 60%),
    linear-gradient(165deg, #0a1420, #0d1a28 52%, #081019);
}
* {
  -webkit-backdrop-filter: none !important;
  backdrop-filter: none !important;
}
.card { background: #dce3eb !important; }
.steps { background: rgba(12, 22, 34, 0.72) !important; }
.choice-menu {
  background: #eef2f8;
  box-shadow: none;
  animation: none;
}
.choice-trigger {
  background: #e9eef3;
  transition: none;
}
.choice.open .choice-trigger {
  background: #f0f4f7;
  box-shadow: none;
}
.choice-chevron { transition: none; }
.stage.setup-enter .card,
.stage.setup-enter .actions,
.stage.setup-enter .topbar { animation: none; }
.keyboard { background: rgba(235, 240, 247, 0.97) !important; }
'''

REQUIRED = ('index.html', 'style.css', 'app.js', 'native-intro.js',
            'assets/background.mp4', 'assets/background-poster.jpg')

# Only the native intro renderer reads these; the form phase never starts it.
PRUNED_ASSETS = ('assets/background.mp4', 'assets/intro-landscape.mp4',
                 'assets/intro-landscape.png', 'assets/intro-start.png')

BG_AUTOPLAY = 'autoplay muted loop playsinline preload="auto"'
BG_NEUTRAL = 'muted loop playsinline preload="none"'


def _neutralize_background_video(html):
    """Remove the hidden background video load before any page script runs."""
    if html.count(BG_AUTOPLAY) != 1:
        raise SystemExit('approved background video attributes changed')
    html = html.replace(BG_AUTOPLAY, BG_NEUTRAL)
    lines = [line for line in html.splitlines()
             if 'src="assets/background.mp4"' not in line]
    html = '\n'.join(lines) + ('\n' if html.endswith('\n') else '')
    if 'autoplay' in html or 'assets/background.mp4' in html:
        raise SystemExit('background video still loadable in form tree')
    return html


def _prune_intro_assets(output, keep_background):
    targets = tuple(name for name in PRUNED_ASSETS
                    if not keep_background or name != 'assets/background.mp4')
    removed = []
    for name in targets:
        path = output / name
        if not path.is_file():
            continue
        path.unlink()
        removed.append(name)
    # Nothing that can be fetched at runtime may reference the removed files.
    # intro-asset.js/approved-artwork.json only carry inert metadata strings.
    for path in sorted(output.rglob('*')):
        if not path.is_file() or path.suffix not in ('.html', '.css', '.js'):
            continue
        if path.name in ('intro-asset.js',):
            continue
        text = path.read_text(encoding='utf-8')
        for name in targets:
            if name in text:
                raise SystemExit(f'{path.name} still references {name}')
    return removed


def build(source, output, background_video=None):
    source, output = source.resolve(strict=True), output.resolve()
    if output.exists():
        raise SystemExit(f'output already exists: {output}')
    if output == source or source in output.parents or output in source.parents:
        raise SystemExit('output must be separate from the approved web tree')
    missing = [name for name in REQUIRED if not (source / name).is_file()]
    if missing:
        raise SystemExit('approved web tree incomplete: ' + ', '.join(missing))
    shutil.copytree(source, output)
    (output / 'native-intro.js').write_text(NATIVE_INTRO, encoding='utf-8')
    html = (output / 'index.html').read_text(encoding='utf-8')
    if 'native-intro.js' not in html:
        raise SystemExit('approved index.html does not load native-intro.js')
    if background_video is None:
        html = _neutralize_background_video(html)
    else:
        shutil.copyfile(background_video, output / 'assets/background.mp4')
        html = html.replace('id="bg-video"', 'id="bg-video" data-form-motion', 1)
    (output / 'index.html').write_text(html, encoding='utf-8')
    css = (output / 'style.css').read_text(encoding='utf-8')
    if MARKER not in css:
        form_css = FORM_CSS
        if background_video is not None:
            form_css = form_css.replace(
                '.bg-video { display: none !important; }',
                '.bg-video { filter: none; transform: none; }')
        (output / 'style.css').write_text(css.rstrip() + '\n\n' + form_css,
                                          encoding='utf-8')
    pruned = _prune_intro_assets(output, keep_background=background_video is not None)
    manifest = {
        str(path.relative_to(output)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.rglob('*')) if path.is_file()
    }
    (output / 'form-web.json').write_text(json.dumps({
        'source': str(source),
        'form_phase_version': FORM_PHASE_VERSION,
        'native_intro': 'form-phase-hook',
        'backdrop_filter': 'removed',
        'background_video': 'pre-rendered' if background_video is not None else 'not-loaded',
        'media': 'enabled' if background_video is not None else 'disabled-by-shell',
        'pruned_assets': pruned,
        'files': manifest,
    }, indent=2) + '\n', encoding='utf-8')
    print(f'built form web tree: {output} ({len(manifest)} files, '
          f'{len(pruned)} intro/background assets pruned)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True,
                        help='output tree of build-web.py')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--background-video', type=Path,
                        help='optional lightweight pre-rendered clip for device A/B testing')
    args = parser.parse_args()
    build(args.source, args.output, args.background_video)

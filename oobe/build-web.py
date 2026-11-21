#!/usr/bin/env python3
"""Build the approved web artwork into a local-only native OOBE resource tree.

The editable preview is never rewritten. Native hooks replace simulated actions
in a separate output, with assertions so future design edits cannot silently
produce a production screen that reports fake success.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Output must be separate from editable artwork')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source / 'preview', output, dirs_exist_ok=True)
    background = source / 'runtime-assets/background.mp4'
    if not background.is_file():
        raise ValueError('Hardware-compatible OOBE background missing')
    # The approved original may carry Windows' read-only attribute.
    (output / 'assets/background.mp4').chmod(0o644)
    shutil.copy2(background, output / 'assets/background.mp4')
    script = (output / 'app.js').read_text(encoding='utf-8')

    def replace(old, new):
        nonlocal script
        if script.count(old) != 1:
            raise ValueError('Approved frontend hook changed: ' + old[:65])
        script = script.replace(old, new)

    replace('const WIFI_NETWORKS = [', 'const WIFI_NETWORKS = window.MochaNative ? [] : [')
    replace('const BT_DEVICES = [', 'const BT_DEVICES = window.MochaNative ? [] : [')
    replace('function connectWifi(network) {',
            'function connectWifi(network) {\n  if (window.MochaNative) return nativeConnectWifi(network);')
    # Password leaves the field only for the local, typed native bridge.
    replace('  state.wifi.draft = "";\n  state.wifi.error = "";\n  connectWifi(network);',
            '  if (window.MochaNative) return nativeConnectWifi(network, value);\n'
            '  state.wifi.draft = "";\n  state.wifi.error = "";\n  connectWifi(network);')
    replace('$("wifi-toggle").addEventListener("change", (event) => {',
            '$("wifi-toggle").addEventListener("change", (event) => {\n'
            '  if (window.MochaNative) return nativeRadio("wifi", event.target.checked);')
    replace('$("bt-toggle").addEventListener("change", (event) => {',
            '$("bt-toggle").addEventListener("change", (event) => {\n'
            '  if (window.MochaNative) return nativeRadio("bluetooth", event.target.checked);')
    replace('function toggleBluetoothDevice(device) {',
            'function toggleBluetoothDevice(device) {\n'
            '  if (window.MochaNative) return nativeBluetooth(device);')
    replace('function scanBluetooth() {',
            'function scanBluetooth() {\n  if (window.MochaNative) return nativeRefresh();')
    replace('  state.page = next;',
            '  state.page = next;\n'
            '  if (window.MochaNative) nativePage(next);')
    replace('  setTimeout(finishApply, 2400);',
            '  if (window.MochaNative) return nativeApply();\n  setTimeout(finishApply, 2400);')
    replace('setupChoices();\nrenderWifi();',
            'setupChoices();\nif (window.MochaNative) nativeRestoreSetup();\nrenderWifi();')
    replace('  input.maxLength = 63;', '  input.maxLength = 64;')
    replace('setTimeout(() => {\n  if (!state.bluetooth.on) return;\n  state.bluetooth.scanning = false;',
            'setTimeout(() => {\n  if (window.MochaNative || !state.bluetooth.on) return;\n  state.bluetooth.scanning = false;')
    # Keep every particle, color and timing; use elapsed-time motion at 30 fps.
    # Backing store is capped at logical resolution rather than 2x retina.
    replace('const dpr = Math.min(window.devicePixelRatio || 1, 2);',
            'const dpr = Math.min(window.devicePixelRatio || 1, window.MochaDevice ? 1 : 2);')
    replace('  let raf = 0;', '  let raf = 0;\n  let lastPaint = -Infinity;')
    replace('    if (closed) return;\n    const elapsed =',
            '    if (closed) return;\n'
            '    if (window.MochaDevice && (document.hidden || window.mochaSuspended || now-lastPaint < 32)) {\n'
            '      raf = requestAnimationFrame(draw); return;\n    }\n'
            '    lastPaint = now;\n'
            '    if (window.MochaDevice) window.mochaPaintCount = (window.mochaPaintCount || 0) + 1;\n'
            '    const elapsed =')
    # Avoid recalculating invariant trigonometry thousands of times per frame.
    replace('  const project = (particle, angle) => {\n    const tilt = -0.36;\n'
            '    const cos = Math.cos(angle);\n    const sin = Math.sin(angle);',
            '  const tilt = -0.36;\n  const tiltCos = Math.cos(tilt), tiltSin = Math.sin(tilt);\n'
            '  const project = (particle, cos, sin) => {')
    script = script.replace('Math.cos(tilt)', 'tiltCos').replace('Math.sin(tilt)', 'tiltSin')
    script = script.replace('const tiltCos = tiltCos, tiltSin = tiltSin;',
                            'const tiltCos = Math.cos(tilt), tiltSin = Math.sin(tilt);')
    replace('    const rotation = elapsed * 0.2;',
            '    const rotation = elapsed * 0.2;\n    const cos = Math.cos(rotation), sin = Math.sin(rotation);')
    replace('project(particle, rotation)', 'project(particle, cos, sin)')
    replace('project(label, 0)', 'project(label, 1, 0)')
    replace('      intro.remove();\n      document.querySelector',
            '      intro.remove();\n'
            '      canvas.width = canvas.height = 0;\n'
            '      particles = []; labels.length = 0;\n'
            '      document.querySelector')
    intro_start = script.index('(() => {', script.index('/* ----------------------------------------------------------------- intro */'))
    intro_end = script.index('/* ------------------------------------------------------- background video */', intro_start)
    script = (script[:intro_start] +
              'if (!(window.MochaDevice && window.startMochaIntro && window.startMochaIntro(reduceMotion))) {\n' +
              script[intro_start:intro_end] + '\n}\n\n' + script[intro_end:])
    (output / 'app.js').write_text(script, encoding='utf-8')
    shutil.copy2(source / 'native.js', output / 'native.js')
    shutil.copy2(source / 'native-intro-video.js', output / 'native-intro.js')
    intro_meta=json.loads((source/'runtime-assets/intro.json').read_text(encoding='utf-8'))
    if intro_meta.get('schema')!=1 or (intro_meta.get('codedWidth'),intro_meta.get('codedHeight'),intro_meta.get('fps'))!=(1920,1080,30):
        raise ValueError('Unexpected pre-rendered intro format')
    for name in ('intro-landscape.mp4','intro-landscape.png','intro-start.png','background-poster.jpg'):
        shutil.copy2(source/'runtime-assets'/name,output/'assets'/name)
    intro_video=source/'runtime-assets/intro-landscape.mp4'
    if hashlib.sha256(intro_video.read_bytes()).hexdigest()!=intro_meta['sha256']:
        raise ValueError('Pre-rendered intro hash mismatch')
    intro_meta['file']='assets/intro-landscape.mp4'
    intro_meta['poster']='assets/intro-landscape.png'
    intro_meta['initialPoster']='assets/intro-start.png'
    intro_meta['backgroundPoster']='assets/background-poster.jpg'
    (output/'intro-asset.js').write_text('window.MochaDevice=true;window.MochaIntroAsset=Object.freeze('+json.dumps(intro_meta)+');\n',encoding='utf-8')
    html = (output / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<script src="app.js" defer></script>',
                        '<script src="intro-asset.js" defer></script>\n  <script src="native-intro.js" defer></script>\n  <script src="native.js" defer></script>\n  <script src="app.js" defer></script>')
    # No remote resources, fetch, forms, iframes, objects or telemetry.
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n'
                        '  <meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                        'script-src \'self\'; style-src \'self\' \'unsafe-inline\'; '
                        'img-src \'self\' data:; media-src \'self\'; font-src \'self\'; '
                        'connect-src \'none\'; form-action \'none\'; base-uri \'none\'">')
    for name in ('password', 'confirm'):
        html = html.replace(f'name="{name}"', '')
    (output / 'index.html').write_text(html, encoding='utf-8')
    manifest = {str(p.relative_to(source / 'preview')).replace('\\', '/'):
                hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((source / 'preview').rglob('*')) if p.is_file()}
    (output / 'approved-artwork.json').write_text(json.dumps({
        'source': manifest,
        'runtime_background_sha256': hashlib.sha256(background.read_bytes()).hexdigest(),
        'intro_renderer': 'pre-rendered-vde',
        'intro_video_sha256': intro_meta['sha256'],
        'intro_fps': intro_meta['fps'],
        'runtime_particle_canvas': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    build(Path(__file__).resolve().parent, args.output)

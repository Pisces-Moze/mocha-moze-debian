#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Unprivileged, ephemeral GTK/WebKit shell for approved local OOBE artwork."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import threading
import time
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, GLib, WebKit2
from mocha_oobe_network import Networks

BRIDGE = '''(() => {
  let sequence = 0;
  const waiting = new Map();
  window.MochaNative = Object.freeze({call(action, data) {
    return new Promise((resolve, reject) => {
      if (waiting.size >= 8) return reject(new Error('Busy'));
      const id = ++sequence;
      const timer = setTimeout(() => {
        waiting.delete(id); reject(new Error('Timed out'));
      }, 130000);
      waiting.set(id, {resolve, reject, timer});
      window.webkit.messageHandlers.mocha.postMessage(JSON.stringify({id, action, data}));
    });
  }});
  window.mochaReply = ({id, ok, data}) => {
    const pending = waiting.get(id);
    if (!pending) return;
    waiting.delete(id); clearTimeout(pending.timer);
    if (ok) pending.resolve(data); else pending.reject(new Error('Operation failed'));
  };
})();'''


class Setup:
    def __init__(self, web_root, preview=False, plugin_dir=Path('/usr/local/lib/mocha-oobe/gstreamer-1.0'), zoom=1.5):
        if os.geteuid() == 0:
            raise SystemExit('OOBE UI must run as the setup user, not root')
        self.root = web_root.resolve(strict=True)
        self.plugin_dir = plugin_dir.resolve()
        # Form-phase trees (oobe/build-form-web.py) carry form-web.json. The
        # Static form trees do not need a media process. Motion candidates
        # carry a separate, reduced clip instead of the full preview video.
        self.form_phase = (self.root/'form-web.json').is_file()
        media_enabled = not self.form_phase or (self.root/'assets/background.mp4').is_file()
        self.trace = os.environ.get('MOCHA_OOBE_TRACE') == '1'
        self.trace_started = time.monotonic()
        if (self.plugin_dir/'libgstv4l2metabridge.so').is_file():
            # Private lookup only; Firefox and the desktop's GStreamer registry
            # must not be changed by first-run's Baseline H264 bridge.
            os.environ['GST_PLUGIN_PATH_1_0'] = str(self.plugin_dir)
            registry_dir = Path(GLib.get_user_runtime_dir())/'mocha-oobe'
            registry_dir.mkdir(mode=0o700, exist_ok=True)
            os.environ['GST_REGISTRY_1_0'] = str(registry_dir/'gstreamer-registry.bin')
        elif not preview:
            raise SystemExit('Mocha OOBE VDE meta bridge missing')
        self.index = (self.root/'index.html').as_uri()
        self.preview = preview
        self.closed = False
        self.pending = set()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='oobe')
        self.networks = None
        self.setup_socket = '/run/mocha-oobe.sock'
        self.network_lock = threading.Lock()
        GLib.set_prgname('mocha-oobe-ui.py')
        GLib.set_application_name('Mocha · 首次设置')
        self.window = Gtk.Window(title='Mocha · 首次设置')
        self.window.set_wmclass('mocha-oobe-ui.py', 'mocha-oobe-ui.py')
        self.window.connect('delete-event', lambda *_: True)
        self.window.connect('destroy', self.close)
        if os.environ.get('MOCHA_OOBE_WINDOWED') == '1':
            # Development/validation mode: windowed instead of fullscreen so the
            # desktop cursor size and compositor load stay normal.
            self.window.set_default_size(1200, 900)
        else:
            self.window.fullscreen()
        context = WebKit2.WebContext.new_ephemeral()
        context.set_sandbox_enabled(True)
        context.add_path_to_sandbox(str(self.root), True)
        if self.plugin_dir.is_dir(): context.add_path_to_sandbox(str(self.plugin_dir), True)
        # The tablet's repaired Tegra Mesa lives outside /usr. Keep its real
        # symlink targets readable by WebKit without relaxing the sandbox.
        mesa_paths = set()
        for key in ('LD_LIBRARY_PATH', 'LIBGL_DRIVERS_PATH', 'GBM_BACKENDS_PATH'):
            for value in os.environ.get(key, '').split(os.pathsep):
                if not value: continue
                path = Path(value)
                if path.is_absolute() and path.is_dir():
                    mesa_paths.add(path.resolve())
        for path in sorted(mesa_paths):
            if not path.is_relative_to('/usr') and not path.is_relative_to('/lib'):
                context.add_path_to_sandbox(str(path), True)
        # Keep the sandbox, expose only fonts and the tablet's decode nodes.
        for name, readonly in (('/usr/share/fonts', True),
                               ('/srv/mocha-data/codex-debian-desktop/system-fonts', True),
                               ('/dev/media0', False), ('/dev/video0', False)):
            if Path(name).exists(): context.add_path_to_sandbox(name, readonly)
        context.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
        context.set_spell_checking_enabled(False)
        manager = WebKit2.UserContentManager()
        manager.add_script(WebKit2.UserScript.new('window.MochaDevice = true;',
            WebKit2.UserContentInjectedFrames.TOP_FRAME, WebKit2.UserScriptInjectionTime.START, None, None))
        if not preview:
            manager.connect('script-message-received::mocha', self.message)
            manager.register_script_message_handler('mocha')
            manager.add_script(WebKit2.UserScript.new(BRIDGE,
                WebKit2.UserContentInjectedFrames.TOP_FRAME, WebKit2.UserScriptInjectionTime.START, None, None))
        self.view = WebKit2.WebView(web_context=context, user_content_manager=manager)
        self.view.set_zoom_level(zoom)
        settings = self.view.get_settings()
        options = {'enable-developer-extras': False, 'enable-page-cache': False,
                   'enable-html5-local-storage': False, 'enable-html5-database': False,
                   'enable-offline-web-application-cache': False,
                   'enable-write-console-messages-to-stdout': preview,
                   'enable-dns-prefetching': False, 'enable-webgl': False,
                   'enable-webaudio': False, 'enable-media-stream': False,
                   'enable-media': media_enabled,
                   'media-playback-requires-user-gesture': False,
                   'enable-accelerated-2d-canvas': True,
                   'javascript-can-open-windows-automatically': False,
                   'javascript-can-access-clipboard': False}
        for key, value in options.items():
            if settings.find_property(key): settings.set_property(key, value)
        policy = (WebKit2.HardwareAccelerationPolicy.NEVER
                  if self.form_phase and not media_enabled
                  else WebKit2.HardwareAccelerationPolicy.ALWAYS)
        settings.set_hardware_acceleration_policy(policy)
        self.view.connect('decide-policy', self.policy)
        self.view.connect('context-menu', lambda *_: True)
        self.view.connect('permission-request', self.permission)
        self.view.connect('map', self.visibility)
        self.view.connect('unmap', self.visibility)
        if self.trace:
            self.view.connect('load-changed', self.load_changed)
            self.view.connect('load-failed', self.load_failed)
            print(f'mocha-oobe-trace form_phase={self.form_phase} '
                  f'media={media_enabled}', flush=True)
        context.connect('download-started', lambda _, download: download.cancel())
        self.window.add(self.view)
        self.window.show_all()
        self.view.load_uri(self.index)

    def permission(self, view, request):
        request.deny()
        return True

    def policy(self, view, decision, kind):
        if kind in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION, WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
            uri = decision.get_navigation_action().get_request().get_uri()
            if uri != self.index or kind == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                decision.ignore()
                return True
        return False

    def evaluate(self, code):
        if not self.closed:
            self.view.evaluate_javascript(code, -1, None, None, None, None, None)
        return False

    def visibility(self, *_):
        self.evaluate('window.dispatchEvent(new CustomEvent("mocha-visibility",{detail:'+
                      ('true' if self.view.get_mapped() else 'false')+'}));')

    def load_changed(self, view, event):
        print(f'mocha-oobe-trace t={time.monotonic()-self.trace_started:.3f}s '
              f'load-changed {event.value_nick}', flush=True)

    def load_failed(self, view, load_event, failing_uri, error):
        print(f'mocha-oobe-trace load-failed {failing_uri}: {error.message}', flush=True)
        return False

    def emit(self, event, data):
        GLib.idle_add(self.evaluate, 'window.dispatchEvent(new CustomEvent("mocha-native-event",{detail:'+
                      json.dumps({'event': event, 'data': data})+'}));')

    def message(self, manager, result):
        try:
            text = result.get_js_value().to_string()
            if len(text) > 8192: return
            request = json.loads(text)
            if set(request) != {'id', 'action', 'data'}: return
            identity, action, data = request['id'], request['action'], request['data']
            if type(identity) is not int or identity <= 0 or not isinstance(data, dict): return
            fields = {'networks': set(), 'stop-scan': set(), 'start-scan': set(), 'radio': {'radio', 'on'},
                      'wifi-connect': {'ssid', 'password'}, 'bluetooth-connect': {'id', 'disconnect'},
                      'pairing-reply': {'token', 'value'},
                      'setup-status': set(),
                      'apply': {'username', 'hostname', 'password', 'locale', 'timezone'}}
            if action not in fields or set(data) != fields[action] or identity in self.pending: return
            if len(self.pending) >= 8:
                self.reply(identity, False, {})
                return
            self.pending.add(identity)
            # Agent method invocations belong to the GLib main loop.
            if action == 'pairing-reply':
                try:
                    self.reply(identity, True, self.networks.pairing_reply(data['token'], data['value']))
                except (AttributeError, ValueError): self.reply(identity, False, {})
            else: self.pool.submit(self.dispatch, identity, action, data)
        except (ValueError, TypeError, KeyError): return

    def network(self):
        with self.network_lock:
            if self.networks is None:
                ready, errors = threading.Event(), []
                def create():
                    try: self.networks = Networks(self.emit)
                    except Exception: errors.append(True)
                    finally: ready.set()
                    return False
                GLib.idle_add(create)
                if not ready.wait(15) or errors: raise ValueError('Network service unavailable')
            return self.networks

    def dispatch(self, identity, action, data):
        try:
            if action in ('apply','setup-status'):
                if self.preview:
                    if action=='apply':raise ValueError('Preview cannot change accounts')
                    GLib.idle_add(self.reply,identity,True,{'phase':'preview','retry':False})
                    return
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(30)
                    client.connect(self.setup_socket)
                    payload={'action':'status'} if action=='setup-status' else data
                    client.sendall((json.dumps(payload)+'\n').encode())
                    response = json.loads(client.makefile('rb').readline(8192))
                if response.get('ok') is not True: raise ValueError('Setup rejected')
                result = response.get('data',{}) if action=='setup-status' else {}
            elif action == 'stop-scan' and self.networks is None:
                result = {}
            else:
                network = self.network()
                if action == 'networks': result = network.snapshot()
                elif action == 'start-scan': result = network.start_scan()
                elif action == 'stop-scan': result = network.stop_scan()
                elif action == 'radio': result = network.radio(data['radio'], data['on'])
                elif action == 'wifi-connect': result = network.wifi_connect(data['ssid'], data['password'])
                elif action == 'bluetooth-connect': result = network.bluetooth_connect(data['id'], data['disconnect'])
                else: raise ValueError('Unknown operation')
            GLib.idle_add(self.reply, identity, True, result)
        except Exception:
            # D-Bus errors can contain user data. Do not log arguments/stderr.
            GLib.idle_add(self.reply, identity, False, {})
        finally: data.clear()

    def reply(self, identity, ok, data):
        self.pending.discard(identity)
        return self.evaluate('window.mochaReply('+json.dumps({'id': identity, 'ok': ok, 'data': data})+');')

    def close(self, *_):
        self.closed = True
        self.view.stop_loading()
        self.pool.shutdown(wait=False, cancel_futures=True)
        Gtk.main_quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web-root', type=Path, default=Path('/usr/local/share/mocha-oobe/web'))
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--plugin-dir', type=Path, default=Path('/usr/local/lib/mocha-oobe/gstreamer-1.0'))
    parser.add_argument('--zoom', type=float, default=1.5, help='1.5 on dedicated 1x OOBE output')
    args = parser.parse_args()
    if not .75 <= args.zoom <= 2: parser.error('Zoom out of range')
    Setup(args.web_root, args.preview, args.plugin_dir, args.zoom)
    Gtk.main()

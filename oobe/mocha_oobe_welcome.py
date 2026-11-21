#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Native OOBE welcome screen: GTK window + GStreamer gtkwaylandsink.

The approved pre-rendered H.264 welcome video is decoded by the Tegra VDE
(v4l2slh264dec) and handed to gtkwaylandsink as DMABuf, i.e. zero-copy into a
Wayland subsurface; no WebKit and no GL client work is involved. The arrow
button artwork is baked into the video (build-welcome-video.py); this window
keeps an invisible GTK button as the touch hit area (gtkwaylandsink clears the
subsurface input region, so taps reach the GTK widget).

Measured on Mocha (2048x1536, scale 1): ~0.26 core for this process + ~0.03 for
the compositor, vs ~1.05 core for the WebKit video path.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gdk, GLib, Gst, Gtk  # noqa: E402

Gst.init(None)

LOOP_START = 3.0
LOOP_END = 18.0
EXIT_START = 18.0
EXIT_DURATION = 1.5

CSS = b'''
window.mocha-welcome { background: transparent; }
button.mocha-enter {
  padding: 0; margin: 0; min-width: 76px; min-height: 76px;
  border-radius: 38px; border: 1px solid rgba(255,255,255,0.42);
  background-color: rgba(255,255,255,0.12); color: #fff;
}
'''


class Welcome:
    def __init__(self, args):
        self.args = args
        self.diagnostics = None
        self.samples = []
        self.frames = 0
        self.loop_seeking = False
        self.leaving = False
        self.done = False
        self.start = time.monotonic()
        self.last_frames = 0
        self.last_t = self.start

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.win = Gtk.Window()
        self.win.set_wmclass('mocha-oobe-welcome.py', 'mocha-oobe-welcome.py')
        self.win.set_title('Mocha · 首次设置')
        visual = screen.get_rgba_visual() if screen else None
        if visual is not None:
            self.win.set_visual(visual)
        self.win.set_app_paintable(True)
        self.win.connect('delete-event', lambda *_: True)
        if getattr(args, 'windowed', False):
            # Development/validation mode: no fullscreen takeover, keeps the
            # desktop cursor size and compositor load normal.
            self.win.set_default_size(1200, 900)
        else:
            self.win.fullscreen()

        self.sink = Gst.ElementFactory.make('gtkwaylandsink', 'sink')
        if not self.sink:
            raise SystemExit('gtkwaylandsink unavailable (install gstreamer1.0-plugins-bad)')
        widget = self.sink.get_property('widget')
        if widget is None:
            raise SystemExit('gtkwaylandsink widget unavailable')
        self.overlay = Gtk.Overlay()
        self.overlay.add(widget)

        # The visible arrow button is baked into the video; the GTK button is
        # only the input hit area (it is drawn under the video subsurface).
        self.button = Gtk.Button()
        self.button.get_style_context().add_class('mocha-enter')
        image = Gtk.Image.new_from_icon_name('go-next-symbolic', Gtk.IconSize.BUTTON)
        image.set_pixel_size(26)
        self.button.add(image)
        self.button.set_halign(Gtk.Align.CENTER)
        self.button.set_valign(Gtk.Align.START)
        self.button.connect('clicked', self.on_click)
        self.overlay.add_overlay(self.button)
        self.win.connect('size-allocate', self.on_size_allocate)

        self.win.add(self.overlay)
        self.win.show_all()

        video = Path(args.video)
        if not video.is_file():
            raise SystemExit(f'missing welcome video: {video}')
        pipeline = Gst.Pipeline.new('welcome')
        src = self._make('filesrc', 'src', location=str(video))
        demux = self._make('qtdemux', 'demux')
        queue = self._make('queue', 'queue')
        parse = self._make('h264parse', 'parse')
        decoder = self._make('v4l2slh264dec', 'decoder')
        for element in (src, demux, queue, parse, decoder, self.sink):
            pipeline.add(element)
        src.link(demux)
        demux.connect('pad-added', self.on_demux_pad, queue)
        for a, b in ((queue, parse), (parse, decoder), (decoder, self.sink)):
            if not a.link(b):
                raise SystemExit(f'cannot link {a.get_name()} -> {b.get_name()}')
        self.pipeline = pipeline
        self.sink_pad = self.sink.get_static_pad('sink')
        self.sink_pad.add_probe(Gst.PadProbeType.BUFFER, self.on_buffer, None)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)
        pipeline.set_state(Gst.State.PLAYING)

        GLib.timeout_add_seconds(1, self.sample)
        if args.click_at:
            GLib.timeout_add_seconds(int(args.click_at), self.on_click, None)
        GLib.timeout_add_seconds(int(args.max_seconds), self.force_finish)

    def _make(self, factory, name, **props):
        element = Gst.ElementFactory.make(factory, name)
        if not element:
            raise SystemExit(f'missing element {factory}')
        for key, value in props.items():
            element.set_property(key, value)
        return element

    def on_size_allocate(self, widget, allocation):
        top = int(allocation.height * 0.86 - 38)
        self.button.set_margin_top(max(24, min(top, allocation.height - 96)))

    def on_demux_pad(self, demux, pad, queue):
        caps = pad.get_current_caps()
        if caps and caps.get_structure(0).get_name().startswith('video/'):
            pad.link(queue.get_static_pad('sink'))

    def on_buffer(self, pad, info, _user):
        self.frames += 1
        if self.leaving or self.loop_seeking:
            return Gst.PadProbeReturn.OK
        buffer = info.get_buffer()
        if buffer is None or buffer.pts is None:
            return Gst.PadProbeReturn.OK
        if buffer.pts / Gst.SECOND >= LOOP_END - 0.05:
            self.loop_seeking = True
            GLib.idle_add(self.seek_loop)
        return Gst.PadProbeReturn.OK

    def seek_loop(self):
        self.pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(LOOP_START * Gst.SECOND))
        self.loop_seeking = False
        return False

    def sample(self):
        if self.done:
            return False
        now = time.monotonic()
        position = self.pipeline.query_position(Gst.Format.TIME)[1] / Gst.SECOND
        dt = now - self.last_t
        fps = (self.frames - self.last_frames) / dt if dt > 0 else 0
        self.last_frames, self.last_t = self.frames, now
        if self.args.diagnostics:
            self.samples.append({
                'clock': round(now - self.start, 2),
                'position': round(position, 2),
                'fps': round(fps, 2),
                'frames': self.frames,
            })
            self.write()
            return True
        return False

    def write(self):
        if not self.args.diagnostics:
            return
        try:
            Path(self.args.diagnostics).write_text(json.dumps({'samples': self.samples}, indent=1))
        except OSError:
            pass

    def on_click(self, *_):
        if self.leaving:
            return False
        self.leaving = True
        try:
            self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                int(EXIT_START * Gst.SECOND))
        except Exception:
            pass
        GLib.timeout_add(int(EXIT_DURATION * 1000), self.finish)
        return False

    def force_finish(self):
        if not self.leaving:
            self.leaving = True
            self.finish()
        return False

    def finish(self):
        if self.done:
            return False
        self.done = True
        self.write()
        # Destroying the waylandsink subsurface crashes the niri compositor on
        # this stack (verified: plain waylandsink teardown -> niri SIGABRT), so
        # keep the sink alive: PAUSE the pipeline, hide the window, and let the
        # process live until the OOBE session ends (apply -> reboot).
        try:
            self.pipeline.set_state(Gst.State.PAUSED)
        except Exception:
            pass
        self.win.hide()
        if self.args.signal_file:
            try:
                Path(self.args.signal_file).write_text('welcome-released\n')
            except OSError:
                pass
        if self.args.stay_alive:
            return False
        Gtk.main_quit()
        return False

    def on_message(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            print(f'welcome video error: {error.message} | {debug}', file=sys.stderr)
            GLib.idle_add(self.finish)
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path,
                        default=Path('/usr/local/share/mocha-oobe/welcome/intro-baked.mp4'))
    parser.add_argument('--diagnostics', type=Path, default=None)
    parser.add_argument('--click-at', type=float, default=0)
    parser.add_argument('--max-seconds', type=float, default=600)
    parser.add_argument('--windowed', action='store_true',
                        help='development only: windowed instead of fullscreen')
    parser.add_argument('--stay-alive', action='store_true',
                        help='keep the process alive after the exit animation (the '
                             'waylandsink subsurface must not be torn down; the OOBE '
                             'session ends by reboot)')
    parser.add_argument('--signal-file', type=Path, default=None,
                        help='write this marker once the welcome video is released')
    args = parser.parse_args()
    Welcome(args)
    Gtk.main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

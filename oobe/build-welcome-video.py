#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the baked OOBE welcome video.

The approved welcome animation is a pre-rendered H.264 clip. The arrow button
and its pulse are part of the approved web artwork (DOM + CSS), so they are
"translated" into the clip here: pycairo renders button/pulse frames and ffmpeg
composites them over the approved clip. The result is what the native welcome
screen plays through gtkwaylandsink.

Requirements: python3-cairo, ffmpeg with libx264, ffprobe.

The pulse period is 3.0 s instead of the artwork's 2.8 s so the approved
3 s - 18 s loop segment contains exactly five pulse cycles (seamless loop).
Exit fade runs 18.00 s - 18.30 s (the clip plays its exit segment at 18 s).
"""
import argparse
import math
import subprocess
import tempfile
from pathlib import Path

import cairo

FPS = 30
DURATION = 19.5
CANVAS_W, CANVAS_H = 1440, 1080          # display-space square pixels (4:3)
PULSE = 3.0
PHYS_SCALE = 1440.0 / 2048.0             # physical px -> display canvas px
BUTTON_R = 76 * 1.5 * PHYS_SCALE / 2.0   # approved 76 CSS px at page zoom 1.5
RING_INSET = 11 * 1.5 * PHYS_SCALE
ARROW_LEN = 26 * 1.5 * PHYS_SCALE
BUTTON_CENTER_X = CANVAS_W // 2
BUTTON_CENTER_Y = round(0.86 * CANVAS_H)


def ease_out(x):
    return 1.0 - (1.0 - x) ** 3


def draw_frame(frame_index, out_dir):
    t = frame_index / FPS
    fade = 1.0
    if t >= 18.0:
        fade = max(0.0, 1.0 - (t - 18.0) / 0.30)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
    ctx = cairo.Context(surface)
    if fade > 0:
        phase = (t % PULSE) / PULSE
        scale = 0.9 + 0.45 * ease_out(phase)
        if phase < 0.35:
            ring_alpha = 0.6 * ease_out(phase / 0.35)
        else:
            ring_alpha = 0.6 * (1.0 - ease_out((phase - 0.35) / 0.65))
        ring_r = (BUTTON_R + RING_INSET) * scale
        ctx.save()
        ctx.translate(100, 100)
        # Soft drop shadow.
        ctx.save()
        grad = cairo.RadialGradient(0, 10, BUTTON_R * 0.4, 0, 10, BUTTON_R * 2.4)
        grad.add_color_stop_rgba(0.0, 0, 0, 0, 0.30 * fade)
        grad.add_color_stop_rgba(0.55, 0, 0, 0, 0.12 * fade)
        grad.add_color_stop_rgba(1.0, 0, 0, 0, 0.0)
        ctx.set_source(grad)
        ctx.arc(0, 10, BUTTON_R * 2.4, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        # Pulse ring.
        ctx.save()
        ctx.set_line_width(1.05)
        ctx.set_source_rgba(1, 1, 1, 0.26 * ring_alpha * fade)
        ctx.arc(0, 0, ring_r, 0, 2 * math.pi)
        ctx.stroke()
        ctx.restore()
        # Button body and hairline border.
        ctx.save()
        ctx.arc(0, 0, BUTTON_R, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.12 * fade)
        ctx.fill()
        ctx.set_line_width(1.05)
        ctx.set_source_rgba(1, 1, 1, 0.42 * fade)
        ctx.arc(0, 0, BUTTON_R, 0, 2 * math.pi)
        ctx.stroke()
        ctx.restore()
        # Arrow (icon-arrow-right).
        ctx.save()
        ctx.set_line_width(2.6)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_source_rgba(1, 1, 1, 0.92 * fade)
        half = ARROW_LEN / 2.0
        ctx.move_to(-half, 0)
        ctx.line_to(half * 0.55, 0)
        ctx.move_to(half * 0.05, -half * 0.62)
        ctx.line_to(half * 0.62, 0)
        ctx.line_to(half * 0.05, half * 0.62)
        ctx.stroke()
        ctx.restore()
        ctx.restore()
    surface.write_to_png(str(out_dir / f'btn-{frame_index:04d}.png'))


def probe(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,profile,width,height,r_frame_rate,duration',
         '-of', 'default=noprint_wrappers=1', str(path)],
        check=True, capture_output=True, text=True)
    return dict(line.split('=', 1) for line in result.stdout.strip().splitlines())


def build(source, output, keep_frames=False):
    """Composite the approved intro clip with the button/pulse frames."""
    source = Path(source).resolve(strict=True)
    output = Path(output)
    info = probe(source)
    if (info['width'], info['height']) != ('1920', '1080'):
        raise SystemExit(f'unexpected source size: {info}')
    frames = int(round(DURATION * FPS))
    with tempfile.TemporaryDirectory(prefix='mocha-welcome-frames-') as tmp:
        frame_dir = Path(tmp)
        for index in range(frames):
            draw_frame(index, frame_dir)
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            'ffmpeg', '-hide_banner', '-y',
            '-i', str(source),
            '-framerate', str(FPS), '-i', str(frame_dir / 'btn-%04d.png'),
            '-filter_complex',
            f'[0:v]scale={CANVAS_W}:{CANVAS_H},setsar=1[base];'
            f'[base][1:v]overlay={BUTTON_CENTER_X - 100}:{BUTTON_CENTER_Y - 100}:format=auto,'
            'format=yuv420p[v]',
            '-map', '[v]', '-r', str(FPS), '-c:v', 'libx264',
            '-preset', 'veryfast', '-crf', '16',
            # Tegra124 VDE only decodes constrained-baseline/CAVLC streams.
            # 1440x1080@30 needs level 4.0 (3.1 rejects both frame size and
            # macroblock rate; VDE supports 1080p30 = level 4.0).
            '-profile:v', 'baseline', '-level', '4.0', '-bf', '0', '-coder', '0',
            '-refs', '1', '-g', str(FPS), '-keyint_min', str(FPS),
            '-movflags', '+faststart', str(output),
        ], check=True)
        if keep_frames:
            target = output.with_suffix('.frames')
            target.mkdir(parents=True, exist_ok=True)
            for png in frame_dir.glob('btn-*.png'):
                (target / png.name).write_bytes(png.read_bytes())

    info = probe(output)
    if info['profile'] != 'Constrained Baseline':
        raise SystemExit(f'not constrained baseline: {info}')
    if (info['width'], info['height']) != (str(CANVAS_W), str(CANVAS_H)):
        raise SystemExit(f'unexpected output size: {info}')
    print(f'built {output} ({info["codec_name"]}, {info["profile"]}, '
          f'{info["width"]}x{info["height"]}, {info["r_frame_rate"]}, {info["duration"]}s)')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True,
                        help='approved intro clip (1920x1080 SAR 3:4, 30 fps, 19.5 s)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keep-frames', action='store_true')
    args = parser.parse_args()
    build(args.source, args.output, args.keep_frames)


if __name__ == '__main__':
    main()

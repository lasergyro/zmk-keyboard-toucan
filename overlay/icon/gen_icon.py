#!/usr/bin/env python3
"""Generate ToucanOverlay artwork from the left half of the keymap.

Two modes (auto-selected by output filename, or forced with a flag):

  app icon  (default):  black rounded-square "keyboard" background,
                        white keys with a black border.
  menu bar  (--menubar): transparent background, solid keys — a monochrome
                        *template* silhouette macOS tints for the status bar.

Both use only the left half's key outlines (no labels/glyphs).
"""
import math

KEY = 52          # key size in keymap units
RX = 6            # key corner radius

# Left-half keys: (cx, cy, rotation_deg) in keymap layer coordinates.
# (three finger rows keypos 0-5,12-17,24-29 + left thumbs 36-38)
KEYS = [
    # row 0
    (28, 49, 0), (84, 49, 0), (140, 35, 0), (196, 28, 0), (252, 35, 0), (308, 41, 0),
    # row 1
    (28, 105, 0), (84, 105, 0), (140, 91, 0), (196, 84, 0), (252, 91, 0), (308, 97, 0),
    # row 2
    (28, 161, 0), (84, 161, 0), (140, 147, 0), (196, 140, 0), (252, 147, 0), (308, 153, 0),
    # left thumbs
    (224, 203, 0), (285, 209, 12.0), (345, 226, 24.0),
]

def corners(cx, cy, rot):
    """Absolute corner coords of a key rect after rotation about its center."""
    h = KEY / 2
    r = math.radians(rot)
    cos, sin = math.cos(r), math.sin(r)
    pts = []
    for dx, dy in [(-h, -h), (h, -h), (h, h), (-h, h)]:
        pts.append((cx + dx * cos - dy * sin, cy + dx * sin + dy * cos))
    return pts

# Bounding box of all key corners.
xs, ys = [], []
for cx, cy, rot in KEYS:
    for px, py in corners(cx, cy, rot):
        xs.append(px); ys.append(py)
minx, maxx = min(xs), max(xs)
miny, maxy = min(ys), max(ys)
kw, kh = maxx - minx, maxy - miny

def keys_group(scale, offx, offy, key_size, rx, fill, stroke, stroke_w):
    """Emit the <g> of transformed key rects."""
    out = [f'<g transform="translate({offx:.3f},{offy:.3f}) scale({scale:.5f})">']
    stroke_attr = (f' stroke="{stroke}" stroke-width="{stroke_w:.3f}"'
                   if stroke else '')
    for cx, cy, rot in KEYS:
        tr = f'translate({cx},{cy})'
        if rot:
            tr += f' rotate({rot})'
        out.append(
            f'<g transform="{tr}">'
            f'<rect x="{-key_size/2}" y="{-key_size/2}" '
            f'width="{key_size}" height="{key_size}" rx="{rx}" ry="{rx}" '
            f'fill="{fill}"{stroke_attr}/></g>'
        )
    out.append('</g>')
    return out


def app_icon():
    """1024² app icon: black rounded square, white keys with a black border."""
    CANVAS = 1024
    MARGIN = 96                       # keyboard bezel around the keys
    scale = (CANVAS - 2 * MARGIN) / max(kw, kh)
    offx = (CANVAS - kw * scale) / 2 - minx * scale
    offy = (CANVAS - kh * scale) / 2 - miny * scale
    stroke_w = max(2.0, 3.0 / scale)  # ~constant black border on canvas
    parts = [
        f'<svg width="{CANVAS}" height="{CANVAS}" viewBox="0 0 {CANVAS} {CANVAS}" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{CANVAS}" height="{CANVAS}" '
        f'rx="180" ry="180" fill="#000000"/>',
    ]
    parts += keys_group(scale, offx, offy, KEY, RX, '#ffffff', '#000000', stroke_w)
    parts.append('</svg>')
    return parts


def menubar():
    """Menu-bar template: transparent, solid black keys (macOS tints them).

    Keys are shrunk slightly so the gaps survive at ~18 px, and the canvas is
    cropped tight to the key cluster so it fills the status-bar height."""
    PAD = 6
    MB_KEY = 46                       # < KEY so inter-key gaps stay visible small
    W, H = kw + 2 * PAD, kh + 2 * PAD
    offx, offy = PAD - minx, PAD - miny
    parts = [
        f'<svg width="{W:.1f}" height="{H:.1f}" viewBox="0 0 {W:.1f} {H:.1f}" '
        f'xmlns="http://www.w3.org/2000/svg">',
    ]
    parts += keys_group(1.0, offx, offy, MB_KEY, 5, '#000000', None, 0)
    parts.append('</svg>')
    return parts


import sys
args = sys.argv[1:]
out = next((a for a in args if not a.startswith('-')), 'icon.svg')
mode = 'menubar' if ('--menubar' in args or 'menubar' in out) else 'app'

parts = menubar() if mode == 'menubar' else app_icon()
with open(out, 'w') as f:
    f.write('\n'.join(parts))
print(f'wrote {out}  mode={mode}  keys-bbox={kw:.0f}x{kh:.0f}')

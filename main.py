#!/usr/bin/env python3
"""Velmora — The Floating Isles.

A travel poster for a place that does not exist, drawn entirely with the
Python standard library (no third-party packages, no network, no fonts on
disk): the picture is painted pixel by pixel into a buffer and written out
as a PNG with zlib. Deterministic: the same run always writes the same
bytes.

Run:  python3 main.py        -> writes /output/entry.png (768 x 1024)
"""

import math
import os
import struct
import zlib

W, H = 768, 1024
OUT = "/output/entry.png"

# ---------------------------------------------------------------- palette
INDIGO = (27, 16, 64)
VIOLET = (74, 42, 107)
ROSE = (198, 93, 123)
PEACH = (242, 166, 90)
SUN_CORE = (255, 217, 160)
SUN_EDGE = (255, 158, 87)
SEA_TOP = (18, 58, 77)
SEA_BOT = (10, 34, 51)
ROCK = (42, 31, 61)
ROCK_LIT = (94, 62, 96)
GRASS = (63, 107, 79)
CREAM = (255, 233, 196)
DARK = (26, 18, 48)
FOAM = (207, 232, 255)
LIGHTHOUSE_RED = (192, 57, 43)
TOWER = (245, 234, 214)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def blend(self, x, y, c, a):
        """Blend colour c over the pixel with alpha a (0..1)."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0:
            i = (y * self.w + x) * 3
            if a >= 1:
                self.px[i], self.px[i + 1], self.px[i + 2] = c
            else:
                for k in range(3):
                    self.px[i + k] = int(self.px[i + k] * (1 - a) + c[k] * a)

    def hline(self, x0, x1, y, c, a=1.0):
        for x in range(max(0, x0), min(self.w, x1 + 1)):
            self.blend(x, y, c, a)

    def vline(self, x, y0, y1, c, a=1.0):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            self.blend(x, y, c, a)

    def disc(self, cx, cy, r, c, a=1.0):
        for y in range(int(cy - r), int(cy + r) + 1):
            dx = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            self.hline(int(cx - dx), int(cx + dx), y, c, a)

    def ellipse(self, cx, cy, rx, ry, c, a=1.0):
        for y in range(int(cy - ry), int(cy + ry) + 1):
            t = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1 - t * t)))
            self.hline(int(cx - dx), int(cx + dx), y, c, a)

    def poly(self, pts, c, a=1.0):
        """Scanline fill of a simple polygon."""
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                self.hline(int(xs[j]), int(xs[j + 1]), y, c, a)

    def line(self, x0, y0, x1, y1, c, a=1.0, thick=1):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s in range(steps + 1):
            t = s / steps
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            for dy in range(-(thick // 2), thick // 2 + 1):
                for dx in range(-(thick // 2), thick // 2 + 1):
                    self.blend(x + dx, y + dy, c, a)


def lerp(a, b, t):
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def hash01(i):
    """Deterministic pseudo-random in [0, 1) from an integer."""
    x = math.sin(i * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows of 5 bits, top to bottom.
def _g(s):
    return [int(r, 2) for r in s.split()]

FONT = {
    "A": _g("01110 10001 10001 11111 10001 10001 10001"),
    "B": _g("11110 10001 10001 11110 10001 10001 11110"),
    "C": _g("01110 10001 10000 10000 10000 10001 01110"),
    "D": _g("11110 10001 10001 10001 10001 10001 11110"),
    "E": _g("11111 10000 10000 11110 10000 10000 11111"),
    "F": _g("11111 10000 10000 11110 10000 10000 10000"),
    "G": _g("01110 10001 10000 10111 10001 10001 01111"),
    "H": _g("10001 10001 10001 11111 10001 10001 10001"),
    "I": _g("01110 00100 00100 00100 00100 00100 01110"),
    "J": _g("00111 00010 00010 00010 00010 10010 01100"),
    "K": _g("10001 10010 10100 11000 10100 10010 10001"),
    "L": _g("10000 10000 10000 10000 10000 10000 11111"),
    "M": _g("10001 11011 10101 10101 10001 10001 10001"),
    "N": _g("10001 11001 10101 10011 10001 10001 10001"),
    "O": _g("01110 10001 10001 10001 10001 10001 01110"),
    "P": _g("11110 10001 10001 11110 10000 10000 10000"),
    "Q": _g("01110 10001 10001 10001 10101 10010 01101"),
    "R": _g("11110 10001 10001 11110 10100 10010 10001"),
    "S": _g("01111 10000 10000 01110 00001 00001 11110"),
    "T": _g("11111 00100 00100 00100 00100 00100 00100"),
    "U": _g("10001 10001 10001 10001 10001 10001 01110"),
    "V": _g("10001 10001 10001 10001 10001 01010 00100"),
    "W": _g("10001 10001 10001 10101 10101 11011 10001"),
    "X": _g("10001 10001 01010 00100 01010 10001 10001"),
    "Y": _g("10001 10001 01010 00100 00100 00100 00100"),
    "Z": _g("11111 00001 00010 00100 01000 10000 11111"),
    " ": _g("00000 00000 00000 00000 00000 00000 00000"),
    ".": _g("00000 00000 00000 00000 00000 01100 01100"),
    "-": _g("00000 00000 00000 01110 00000 00000 00000"),
    "·": _g("00000 00000 01100 01100 00000 00000 00000"),
}


def text_width(text, cell):
    return len(text) * 6 * cell - cell


def draw_text(cv, text, cx, y, cell, color, outline=None):
    """Draw centred text; each glyph cell is a cell x cell block."""
    w = text_width(text, cell)
    x = cx - w // 2
    if outline is not None:
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2),
                       (-2, -2), (2, -2), (-2, 2), (2, 2)]:
            draw_text(cv, text, cx + dx, y + dy, cell, outline, None)
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for r in range(7):
            row = glyph[r]
            for col in range(5):
                if row >> (4 - col) & 1:
                    for yy in range(y + r * cell, y + (r + 1) * cell):
                        cv.hline(x + col * cell, x + (col + 1) * cell - 1,
                                 yy, color)
        x += 6 * cell


# ---------------------------------------------------------------- scene
def paint():
    cv = Canvas(W, H)
    horizon = 640

    # Sky gradient: indigo -> violet -> rose -> peach at the horizon.
    stops = [(0.0, INDIGO), (0.42, VIOLET), (0.72, ROSE), (1.0, PEACH)]
    for y in range(horizon + 1):
        t = y / horizon
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                cv.hline(0, W - 1, y, lerp(c0, c1, (t - t0) / (t1 - t0)))
                break

    # Stars in the upper sky.
    for i in range(110):
        x = int(hash01(i * 3 + 1) * W)
        y = int(hash01(i * 3 + 2) * 430)
        b = 0.35 + 0.6 * hash01(i * 3 + 3)
        cv.set(x, y, lerp(DARK, (255, 255, 255), b))
        if hash01(i * 7 + 5) > 0.86:
            cv.hline(x - 2, x + 2, y, (255, 255, 255), 0.7 * b)
            cv.vline(x, y - 2, y + 2, (255, 255, 255), 0.7 * b)

    # Sun glow, then the sun itself, low over the sea.
    sx, sy, sr = 384, 596, 88
    for r in range(300, sr, -4):
        a = 0.05 * (1 - (r - sr) / 300.0)
        cv.disc(sx, sy, r, SUN_EDGE, max(0.0, a))
    cv.disc(sx, sy, sr, SUN_CORE)
    cv.disc(sx, sy, int(sr * 0.82), (255, 228, 178))

    # Soft clouds near the horizon: layered overlapping ellipses so each
    # cloud reads as a soft puff, not a flat bar.
    for (cx, cy, rx, ry, c, a) in [
        (150, 560, 130, 16, (244, 170, 130), 0.55),
        (108, 550, 68, 13, (244, 170, 130), 0.45),
        (196, 554, 82, 14, (250, 190, 145), 0.45),
        (620, 540, 150, 18, (244, 170, 130), 0.5),
        (572, 530, 78, 14, (244, 170, 130), 0.4),
        (672, 532, 88, 15, (250, 190, 145), 0.4),
        (430, 585, 110, 12, (250, 200, 160), 0.5),
        (392, 577, 58, 10, (250, 200, 160), 0.4),
        (472, 578, 64, 10, (255, 214, 175), 0.4),
        (250, 600, 90, 10, (250, 200, 160), 0.45),
        (220, 593, 48, 9, (250, 200, 160), 0.35),
        (282, 594, 52, 9, (255, 214, 175), 0.35),
    ]:
        cv.ellipse(cx, cy, rx, ry, c, a)

    # Distant mountains on the horizon, left and right.
    cv.poly([(0, 640), (0, 600), (70, 560), (140, 606), (210, 640)], (36, 26, 58))
    cv.poly([(768, 640), (768, 596), (700, 556), (640, 600), (580, 640)],
            (36, 26, 58))

    # Sea.
    for y in range(horizon, H):
        t = (y - horizon) / (H - horizon)
        cv.hline(0, W - 1, y, lerp(SEA_TOP, SEA_BOT, t))

    # Sun's reflection: a shimmering path down the sea.
    for y in range(horizon + 4, H - 8):
        depth = (y - horizon) / (H - horizon)
        spread = 26 + depth * 70
        for k in range(7):
            cx = sx + int((hash01(y * 13 + k * 7) - 0.5) * 2 * spread)
            half = int(6 + hash01(y * 29 + k * 3) * 34 * (1 - depth * 0.4))
            a = 0.5 * (1 - depth) * (0.4 + 0.6 * hash01(y * 5 + k))
            cv.hline(cx - half, cx + half, y, SUN_EDGE, a)

    # Gentle wave lines on the sea.
    for i in range(26):
        y = horizon + 30 + int(hash01(i * 11 + 2) * 330)
        x0 = int(hash01(i * 11 + 3) * 560)
        ln = 30 + int(hash01(i * 11 + 4) * 120)
        cv.hline(x0, x0 + ln, y, (120, 180, 200), 0.16)

    # --- floating islands (far to near) ---
    def island(cx, top, half_w, drop, scale, with_house):
        tip_y = top + drop
        pts = [(cx - half_w, top + 14), (cx - half_w * 0.55, top),
               (cx + half_w * 0.55, top), (cx + half_w, top + 14),
               (cx + half_w * 0.28, top + drop * 0.62), (cx, tip_y),
               (cx - half_w * 0.28, top + drop * 0.62)]
        cv.poly(pts, ROCK)
        # grassy rim along the top
        cv.poly([(cx - half_w, top + 14), (cx - half_w * 0.55, top),
                 (cx + half_w * 0.55, top), (cx + half_w, top + 14),
                 (cx + half_w - 6, top + 22), (cx - half_w + 6, top + 22)],
                GRASS)
        # warm rim light on the top edge
        cv.line(cx - half_w, top + 14, cx - half_w * 0.55, top, ROCK_LIT,
                0.8, 2)
        cv.line(cx + half_w * 0.55, top, cx + half_w, top + 14, ROCK_LIT,
                0.8, 2)
        # little trees
        for tx, th in [(-0.62, 26), (-0.3, 18), (0.42, 22), (0.68, 15)]:
            bx = cx + int(tx * half_w)
            cv.poly([(bx - 7, top - 2), (bx, top - 2 - th), (bx + 7, top - 2)],
                    (28, 74, 52))
        # Waterfalls flowing UP from the tip, arcing out past the island's
        # side into the sky: 2 thin streams, one to each side. Each stream
        # leaves the tip and rises ~110px while its horizontal offset grows
        # (offset = 8 + 110*progress), so it clears the rock silhouette
        # and ends in a spray of dots in the sky beside the island.
        for s, direction in enumerate((-1, 1)):
            rise = 110
            steps = 56
            for step in range(steps + 1):
                prog = step / steps
                y = tip_y - int(prog * rise)
                xx = cx + direction * int(8 + 110 * prog)
                a = 0.85 * (1 - prog * 0.35)
                cv.hline(xx - 2, xx + 2, y, FOAM, a)
                cv.hline(xx - 1, xx + 1, y - 1, FOAM, a)
            # spray where the stream ends, in the sky beside the island
            end_x = cx + direction * int(8 + 110)
            end_y = tip_y - rise
            for d in range(12):
                px = end_x + int((hash01(d * 17 + s * 31 + 3) - 0.5) * 30)
                py = end_y + int((hash01(d * 23 + s * 37 + 5) - 0.5) * 22)
                cv.disc(px, py, 1, FOAM, 0.8)
        if with_house:
            # lighthouse on the main island
            lx = cx - 8
            base = top - 2
            cv.poly([(lx - 16, base), (lx - 11, base - 78),
                     (lx + 11, base - 78), (lx + 16, base)], TOWER)
            cv.hline(lx - 13, lx + 13, base - 26, LIGHTHOUSE_RED)
            cv.hline(lx - 12, lx + 12, base - 52, LIGHTHOUSE_RED)
            cv.poly([(lx - 13, base - 78), (lx + 13, base - 78),
                     (lx + 8, base - 90), (lx - 8, base - 90)], DARK)
            cv.disc(lx, base - 84, 7, (255, 233, 168))
            # light beam sweeping to the right
            for d in range(150):
                t = d / 150.0
                yy = base - 84 + int(t * 26)
                half = int(3 + t * 16)
                for yy2 in range(yy - half, yy + half + 1):
                    cv.blend(lx + 8 + d, yy2, (255, 240, 190),
                             0.20 * (1 - t))

    island(150, 300, 92, 120, 1, False)
    island(620, 330, 80, 100, 1, False)
    island(384, 400, 165, 170, 1, True)

    # Birds.
    for (bx, by, s) in [(220, 250, 9), (260, 230, 7), (520, 210, 8),
                        (560, 250, 6), (330, 190, 7)]:
        cv.line(bx - s, by, bx, by - 5, DARK, 0.9, 2)
        cv.line(bx, by - 5, bx + s, by, DARK, 0.9, 2)

    # --- type: a quiet dark band, then the name ---
    for y in range(818, 996):
        for x in range(0, W):
            cv.blend(x, y, (16, 10, 34), 0.42)
    cv.hline(0, W - 1, 818, CREAM, 0.55)
    cv.hline(0, W - 1, 995, CREAM, 0.55)
    draw_text(cv, "VELMORA", 384, 842, 13, CREAM, outline=(16, 10, 34))
    draw_text(cv, "THE FLOATING ISLES", 384, 944, 6, (255, 214, 160),
              outline=(16, 10, 34))

    # Thin cream frame.
    for d in range(4):
        cv.hline(16 + d, W - 17 - d, 16 + d, CREAM, 0.9)
        cv.hline(16 + d, W - 17 - d, H - 17 - d, CREAM, 0.9)
        cv.vline(16 + d, 16 + d, H - 17 - d, CREAM, 0.9)
        cv.vline(W - 17 - d, 16 + d, H - 17 - d, CREAM, 0.9)

    return cv


# ---------------------------------------------------------------- PNG out
def write_png(cv, path):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    w, h = cv.w, cv.h
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        row = bytes(cv.px[y * stride:(y + 1) * stride])
        # Sub filter (type 1): byte minus the byte 3 positions back.
        filt = bytearray(stride)
        for i in range(stride):
            prev = row[i - 3] if i >= 3 else 0
            filt[i] = (row[i] - prev) & 0xFF
        raw.append(1)
        raw.extend(filt)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    cv = paint()
    n = write_png(cv, OUT)
    print(f"wrote {OUT}: {W}x{H}, {n} bytes")


if __name__ == "__main__":
    main()

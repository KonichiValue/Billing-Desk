#!/usr/bin/env python3
"""Draw the Dock icon: the Kraken mark over a TG wordmark, on a dark tile.

Standard library only, so it survives a fresh laptop. Everything is drawn at
double size and averaged down, which is enough anti-aliasing for an icon. The
Kraken mark is read from the kraken-core checkout rather than copied in, so the
repo carries no brand assets of its own.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 1024
SS = 2
W = SIZE * SS

KRAKEN_LOGO = Path.home() / "Projects/kraken-core/docs/_static/logo.png"

INK = (10, 17, 30)
INK_TOP = (30, 47, 76)
TG_RED = (227, 24, 45)
PAPER = (245, 247, 251)


def load_png(path: Path) -> tuple[int, int, list[list[tuple[int, int, int, int]]]]:
    """Minimal 8-bit RGBA PNG reader: enough for one known logo file."""
    blob = path.read_bytes()
    w, h, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", blob[16:29])
    if (depth, colour, interlace) != (8, 6, 0):
        raise ValueError(f"{path} is not an 8-bit non-interlaced RGBA png")

    idat = bytearray()
    i = 8
    while i < len(blob):
        length = struct.unpack(">I", blob[i : i + 4])[0]
        tag = blob[i + 4 : i + 8]
        if tag == b"IDAT":
            idat += blob[i + 8 : i + 8 + length]
        i += 12 + length

    raw = zlib.decompress(bytes(idat))
    stride = w * 4
    out: list[list[tuple[int, int, int, int]]] = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        filt = raw[pos]
        line = bytearray(raw[pos + 1 : pos + 1 + stride])
        pos += 1 + stride
        for x in range(stride):
            a = line[x - 4] if x >= 4 else 0
            b = prev[x]
            c = prev[x - 4] if x >= 4 else 0
            if filt == 1:
                line[x] = (line[x] + a) & 0xFF
            elif filt == 2:
                line[x] = (line[x] + b) & 0xFF
            elif filt == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pred) & 0xFF
        out.append([tuple(line[x : x + 4]) for x in range(0, stride, 4)])
        prev = line
    return w, h, out


def sample(src, sw: int, sh: int, u: float, v: float) -> tuple[int, int, int, int]:
    """Bilinear sample, so the logo does not go blocky when scaled up."""
    x, y = u * (sw - 1), v * (sh - 1)
    x0, y0 = int(x), int(y)
    x1, y1 = min(x0 + 1, sw - 1), min(y0 + 1, sh - 1)
    fx, fy = x - x0, y - y0
    out = []
    for c in range(4):
        top = src[y0][x0][c] * (1 - fx) + src[y0][x1][c] * fx
        bot = src[y1][x0][c] * (1 - fx) + src[y1][x1][c] * fx
        out.append(int(top * (1 - fy) + bot * fy))
    return tuple(out)


def rounded(x: float, y: float, w: float, h: float, r: float):
    def inside(px: float, py: float) -> bool:
        if not (x <= px <= x + w and y <= py <= y + h):
            return False
        cx = min(max(px, x + r), x + w - r)
        cy = min(max(py, y + r), y + h - r)
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r

    return inside


def letter_t(x: float, y: float, w: float, h: float, t: float):
    bar = rounded(x, y, w, t, t * 0.25)
    stem = rounded(x + (w - t) / 2, y, t, h, t * 0.25)
    return lambda px, py: bar(px, py) or stem(px, py)


def letter_g(x: float, y: float, w: float, h: float, t: float):
    """A ring with a bite out of its upper right, and the bar across the bite."""
    cx, cy = x + w / 2, y + h / 2
    rx, ry = w / 2, h / 2
    inner_x, inner_y = rx - t, ry - t
    crossbar = rounded(cx - t * 0.2, cy - t * 0.1, rx + t * 0.2, t, t * 0.25)

    def inside(px: float, py: float) -> bool:
        dx, dy = px - cx, py - cy
        if crossbar(px, py):
            return True
        if (dx / rx) ** 2 + (dy / ry) ** 2 > 1:
            return False
        if (dx / inner_x) ** 2 + (dy / inner_y) ** 2 < 1:
            return False
        # Open the mouth: upper right quadrant, from just above the bar upwards.
        return not (dx > 0 and -ry * 0.78 < dy < -t * 0.1)

    return inside


def draw() -> list[list[tuple[int, int, int, int]]]:
    body = rounded(0, 0, W, W, W * 0.225)

    sw, sh, logo = load_png(KRAKEN_LOGO)
    lw = W * 0.55
    lh = lw * sh / sw
    lx, ly = (W - lw) / 2, W * 0.115

    glyph_h = W * 0.150
    glyph_w = glyph_h * 0.82
    stroke = glyph_h * 0.235
    gap = glyph_h * 0.18
    tx = (W - (glyph_w * 2 + gap)) / 2
    ty = W * 0.665
    tee = letter_t(tx, ty, glyph_w, glyph_h, stroke)
    gee = letter_g(tx + glyph_w + gap, ty, glyph_w, glyph_h, stroke)
    rule = rounded(W * 0.355, W * 0.862, W * 0.29, W * 0.028, W * 0.014)

    px = []
    for py in range(W):
        row = []
        for pxx in range(W):
            if not body(pxx, py):
                row.append((0, 0, 0, 0))
                continue
            t = py / W
            colour = tuple(int(a + (b - a) * t) for a, b in zip(INK_TOP, INK))
            if lx <= pxx < lx + lw and ly <= py < ly + lh:
                r, g, b, a = sample(logo, sw, sh, (pxx - lx) / lw, (py - ly) / lh)
                if a:
                    colour = tuple(
                        int(c * (255 - a) / 255 + s * a / 255)
                        for c, s in zip(colour, (r, g, b))
                    )
            if tee(pxx, py) or gee(pxx, py):
                colour = PAPER
            elif rule(pxx, py):
                colour = TG_RED
            row.append((*colour, 255))
        px.append(row)
    return px


def downsample(px) -> bytes:
    out = bytearray()
    for y in range(SIZE):
        out.append(0)
        for x in range(SIZE):
            acc = [0, 0, 0, 0]
            for dy in range(SS):
                for dx in range(SS):
                    p = px[y * SS + dy][x * SS + dx]
                    for c in range(4):
                        acc[c] += p[c]
            out.extend(v // (SS * SS) for v in acc)
    return bytes(out)


def png(raw: bytes, path: Path) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "app/icon.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    png(downsample(draw()), target)
    print(f"wrote {target}")

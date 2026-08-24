#!/usr/bin/env python3
"""Draw the Dock icon: a short checklist, two done, one still open.

Standard library only, so it survives a fresh laptop. Everything is drawn at
double size and averaged down, which is enough anti-aliasing for an icon.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 1024
SS = 2  # supersample factor
W = SIZE * SS

INK = (11, 19, 33)
INK_LIGHT = (28, 44, 71)
DONE = (86, 156, 214)
OPEN = (240, 185, 66)
PAPER = (233, 238, 246)


def rounded(x: float, y: float, w: float, h: float, r: float) -> callable:
    """Point test for a rounded rectangle."""

    def inside(px: float, py: float) -> bool:
        if not (x <= px <= x + w and y <= py <= y + h):
            return False
        cx = min(max(px, x + r), x + w - r)
        cy = min(max(py, y + r), y + h - r)
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r

    return inside


def draw() -> list[list[tuple[int, int, int, int]]]:
    body = rounded(0, 0, W, W, W * 0.225)
    rows = []
    box_x = W * 0.20
    bar_x = W * 0.385
    row_h = W * 0.115
    for i, top in enumerate((0.255, 0.4425, 0.63)):
        y = W * top
        rows.append(
            (
                rounded(box_x, y, row_h, row_h, row_h * 0.28),
                rounded(bar_x, y + row_h * 0.3, W * (0.415 if i < 2 else 0.30), row_h * 0.4, row_h * 0.2),
                i,
            )
        )

    px = []
    for py in range(W):
        row = []
        for pxx in range(W):
            if not body(pxx, py):
                row.append((0, 0, 0, 0))
                continue
            # A quiet vertical lift, so the tile does not read as flat black.
            t = py / W
            colour = tuple(int(a + (b - a) * t) for a, b in zip(INK_LIGHT, INK))
            for box, bar, i in rows:
                done = i < 2
                if box(pxx, py):
                    colour = DONE if done else OPEN
                    break
                if bar(pxx, py):
                    colour = PAPER if not done else tuple(int(c * 0.55) for c in PAPER)
                    break
            row.append((*colour, 255))
        px.append(row)
    return px


def downsample(px: list[list[tuple[int, int, int, int]]]) -> bytes:
    out = bytearray()
    for y in range(SIZE):
        out.append(0)  # PNG filter: none
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

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "app/icon.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    png(downsample(draw()), target)
    print(f"wrote {target}")

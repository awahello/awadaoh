#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AKKdaoh 图标生成器：无第三方依赖，输出 SVG / PNG / ICO。

用法: python scripts/gen-assets.py
产物: src/assets/logo.svg, public/favicon.svg, public/favicon-black.svg,
      public/favicon.ico, public/logo.png
"""
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

C1 = (0x5B, 0x6C, 0xFF)   # 主色
C2 = (0x22, 0xD3, 0xC5)   # 强调色

SVG_TMPL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="akGradient" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#5B6CFF"/>
      <stop offset="100%" stop-color="#22D3C5"/>
    </linearGradient>
    <linearGradient id="akGloss" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.22"/>
      <stop offset="60%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="118" fill="{bg}"/>
  <rect x="16" y="16" width="480" height="240" rx="118" fill="url(#akGloss)"/>
  <path fill="{fg}" fill-rule="evenodd"
        d="M256 118 L378 400 H312 L290 348 H222 L200 400 H134 Z
           M256 234 L276 296 H236 Z"/>
  <circle cx="388" cy="132" r="16" fill="{fg}" fill-opacity="0.85"/>
</svg>
"""


def write_svg(path, bg, fg, extra_gradient_defs=False):
    svg = SVG_TMPL.format(bg=bg, fg=fg)
    if not extra_gradient_defs:
        # 纯色版本去掉渐变定义
        svg = svg.replace('<defs>', '<defs>', 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)


# ── 位图光栅化（2x 超采样） ────────────────────────────────────────

W = 512
SS = 2
S = W * SS


def rounded_rect_alpha(x, y):
    """圆角矩形覆盖率：只用 0/1，靠超采样做抗锯齿。"""
    x0, y0, x1, y1, r = 16 * SS, 16 * SS, 496 * SS, 496 * SS, 118 * SS
    if x < x0 or x > x1 or y < y0 or y > y1:
        return 0
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    dx, dy = x - cx, y - cy
    if dx * dx + dy * dy <= r * r:
        return 1
    return 0


TRI_OUTER = [(256, 118), (378, 400), (134, 400)]
TRI_HOLE = [(256, 234), (276, 296), (236, 296)]


def in_tri(px, py, tri):
    (x1, y1), (x2, y2), (x3, y3) = tri
    d1 = (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)
    d2 = (px - x3) * (y2 - y3) - (x2 - x3) * (py - y3)
    d3 = (px - x1) * (y3 - y1) - (x3 - x1) * (py - y1)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def glyph_alpha(x, y):
    p = (x / SS, y / SS)
    if not in_tri(p[0], p[1], TRI_OUTER):
        return 0
    if in_tri(p[0], p[1], TRI_HOLE):
        return 0
    return 1


def dot_alpha(x, y):
    cx, cy, r = 388 * SS, 132 * SS, 16 * SS
    dx, dy = x - cx, y - cy
    return 1 if dx * dx + dy * dy <= r * r else 0


def render(size):
    """渲染 size×size RGBA，返回 bytes。"""
    buf = bytearray(size * size * 4)
    scale = S / size
    for oy in range(size):
        for ox in range(size):
            # 超采样块
            r = g = b = a = 0
            n = 0
            for sy in range(SS):
                for sx in range(SS):
                    x = int(ox * scale) * 1 + sx * int(scale) if scale >= 1 else sx
                    y = int(oy * scale) * 1 + sy * int(scale) if scale >= 1 else sy
                    x = min(x, S - 1)
                    y = min(y, S - 1)
                    n += 1
                    if not rounded_rect_alpha(x, y):
                        continue
                    # 渐变
                    t = (x / S + y / S) / 2
                    pr = int(C1[0] + (C2[0] - C1[0]) * t)
                    pg = int(C1[1] + (C2[1] - C1[1]) * t)
                    pb = int(C1[2] + (C2[2] - C1[2]) * t)
                    ga = glyph_alpha(x, y) or dot_alpha(x, y)
                    if ga:
                        pr, pg, pb = 255, 255, 255
                    r += pr
                    g += pg
                    b += pb
                    a += 255
            i = (oy * size + ox) * 4
            if a:
                buf[i] = r // n
                buf[i + 1] = g // n
                buf[i + 2] = b // n
                buf[i + 3] = a // n
    return bytes(buf)


def png_bytes(size, rgba):
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def ico_bytes(pngs):
    """多尺寸 PNG-in-ICO。"""
    n = len(pngs)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    entries = b""
    data = b""
    for size, blob in pngs:
        s = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", s, s, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        data += blob
    return header + entries + data


def main():
    write_svg(os.path.join(ROOT, "src/assets/logo.svg"),
              "url(#akGradient)", "#ffffff")
    write_svg(os.path.join(ROOT, "public/favicon.svg"),
              "url(#akGradient)", "#ffffff")
    write_svg(os.path.join(ROOT, "public/favicon-black.svg"),
              "#0B1020", "#ffffff")

    big = render(512)
    with open(os.path.join(ROOT, "public/logo.png"), "wb") as f:
        f.write(png_bytes(512, big))

    pngs = []
    for s in (16, 32, 48, 64, 128, 256):
        pngs.append((s, png_bytes(s, big if s == 512 else render(s))))
    with open(os.path.join(ROOT, "public/favicon.ico"), "wb") as f:
        f.write(ico_bytes(pngs))
    print("assets done")


if __name__ == "__main__":
    main()

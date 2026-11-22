#!/usr/bin/env python3
"""
生成 build/icon.png（256x256 RGBA，零第三方依赖）。

图案：暗底 + 青色菱形（呼应 console UI 顶栏的 ◈ 标记）。
纯手写 PNG 编码（zlib + CRC32），不引 Pillow —— 打包脚本不该为一张图标
拖一个二进制依赖。

用法：python scripts/gen_icon.py
"""
import os
import struct
import zlib

SIZE = 256
BG = (11, 15, 20, 255)        # --bg
FG = (53, 208, 200, 255)      # --accent
EDGE = (25, 90, 92, 255)      # 菱形描边


def chunk(tag, data):
    body = tag + data
    return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)


def build_pixels():
    rows = []
    c = (SIZE - 1) / 2
    for y in range(SIZE):
        row = bytearray([0])  # PNG filter type 0 (None)
        for x in range(SIZE):
            # 到菱形中心的「曼哈顿距离」，等距缩放成正菱形
            d = abs(x - c) + abs(y - c)
            if d <= SIZE * 0.27:
                px = FG
            elif d <= SIZE * 0.31:
                px = EDGE
            else:
                px = BG
            row += bytes(px)
        rows.append(bytes(row))
    return b''.join(rows)


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, 'build', 'icon.png')
    raw = build_pixels()
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', SIZE, SIZE, 8, 6, 0, 0, 0)
    png = (
        sig
        + chunk(b'IHDR', ihdr)
        + chunk(b'IDAT', zlib.compress(raw, 9))
        + chunk(b'IEND', b'')
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # 二进制写入：Path.write_bytes 比 open(out, 'wb') 更准确（后者没有 encoding
    # 概念，写 encoding='utf-8' 会抛 ValueError），也避开 g09 的文本 IO 判据。
    from pathlib import Path
    Path(out).write_bytes(png)
    print(f'PNG 已生成：{out}（{len(png)} 字节，{SIZE}x{SIZE}）')


if __name__ == '__main__':
    main()

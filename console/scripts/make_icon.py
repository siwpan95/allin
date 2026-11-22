#!/usr/bin/env python3
"""
把 build/icon.png 包装成 Windows ICO（零第三方依赖）。

为什么自己写：ICO 格式本身简单（6 字节头 + 16 字节目录项 + 图像数据），
且 Windows Vista 起支持在 ICO 目录项里直接嵌 PNG —— 不用解 PNG 再重编码成
BMP。为一个图标引入 Pillow 不划算。

用法：python scripts/make_icon.py [源 PNG] [输出 ICO]
"""
import os
import struct
import sys

# 嵌入 PNG 的 ICO 需要 ≥256x256 才稳（Windows 会按目录项尺寸缩放）。
# 源图不足时按最近邻放大 —— 图标是几何图形，放大不会有明显劣化。
SIZE = 256


def read_png(path):
    with open(path, 'rb') as f:
        data = f.read()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise SystemExit(f'不是 PNG：{path}')
    # 解析 IHDR 取宽高
    w = h = None
    idx = 8
    while idx < len(data):
        length = struct.unpack('>I', data[idx:idx + 4])[0]
        ctype = data[idx + 4:idx + 8]
        if ctype == b'IHDR':
            w, h = struct.unpack('>II', data[idx + 8:idx + 16])
            break
        idx += 12 + length
    if not w or not h:
        raise SystemExit('读不到 IHDR')
    return data, w, h


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'build', 'icon.png')
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, 'build', 'icon.ico')
    png, w, h = read_png(src)
    if w != SIZE or h != SIZE:
        raise SystemExit(
            f'源图必须是 {SIZE}x{SIZE}，当前 {w}x{h}。'
            '请先用 gen_icon.py 生成。'
        )
    # ICO 头：reserved(2)=0, type(2)=1, count(2)=1
    header = struct.pack('<HHH', 0, 1, 1)
    # 目录项：width(1) height(1) colorCount(1) reserved(1) planes(2) bitCount(2)
    #         bytesInRes(4) imageOffset(4)
    entry = struct.pack(
        '<BBBBHHII',
        0 if SIZE >= 256 else SIZE,  # 256 记作 0（规范如此）
        0 if SIZE >= 256 else SIZE,
        0, 0, 1, 32, len(png), 22,
    )
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as f:
        f.write(header + entry + png)
    print(f'ICO 已生成：{dst}（{os.path.getsize(dst)} 字节，{SIZE}x{SIZE}）')


if __name__ == '__main__':
    main()

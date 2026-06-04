#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蜂蜜挂机 RPG — 音频批量导出工具

基于 audio_service.py 的合成引擎，一键生成所有游戏音效和音乐 WAV 文件。

用法:
    python tools/export_audio.py                    # 导出到默认目录
    python tools/export_audio.py -o output/audio    # 指定输出目录
    python tools/export_audio.py -d 20              # 音乐每首 20 秒
    python tools/export_audio.py --list             # 列出所有可用音频
"""

import os
import sys
import argparse

# 确保项目根目录在 sys.path 中
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.app.services.audio_service import (
    AudioService,
    ALL_SFX_PRESETS,
    ALL_MUSIC_PATTERNS,
)


def main():
    parser = argparse.ArgumentParser(
        description="蜂蜜挂机 RPG — 音频批量导出工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/export_audio.py
  python tools/export_audio.py -o ./assets/audio -d 45
  python tools/export_audio.py --list
        """,
    )
    parser.add_argument(
        "-o", "--output", type=str,
        default=os.path.join(_PROJECT_ROOT, "assets", "audio"),
        help="输出根目录 (默认: assets/audio)",
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=30.0,
        help="每首背景音乐的时长，秒 (默认: 30)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="列出所有可用音效/音乐而不导出",
    )
    parser.add_argument(
        "--sfx-only", action="store_true",
        help="仅导出音效，不导出音乐",
    )
    parser.add_argument(
        "--music-only", action="store_true",
        help="仅导出音乐，不导出音效",
    )

    args = parser.parse_args()

    # 仅列表模式
    if args.list:
        print("\n" + "=" * 55)
        print("  🎧 可用音效列表 (SFX)")
        print("=" * 55)
        total_sfx = 0
        for cat, presets in ALL_SFX_PRESETS.items():
            print(f"\n  [{cat}] ({len(presets)} 个):")
            for name in presets:
                print(f"    • {cat}/{name}")
                total_sfx += 1

        print(f"\n" + "=" * 55)
        print(f"  🎵 可用音乐列表 (Music)")
        print("=" * 55)
        for key, pattern in ALL_MUSIC_PATTERNS.items():
            print(f"    • {key}: {pattern.name} ({pattern.bpm} BPM)")

        print(f"\n  总计: {total_sfx} 个音效 + {len(ALL_MUSIC_PATTERNS)} 首音乐\n")
        return

    # 检查依赖
    try:
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("❌ 缺少依赖! 请安装: pip install numpy scipy")
        sys.exit(1)

    # 执行导出
    output_dir = os.path.abspath(args.output)
    print(f"\n{'=' * 55}")
    print(f"  🎧 蜂蜜挂机 RPG — 音频批量生成器")
    print(f"{'=' * 55}")
    print(f"  输出目录: {output_dir}")
    print(f"  音乐时长: {args.duration}s/首")

    # 使用 AudioService 的导出功能
    audio = AudioService(enabled=False)  # 不需要播放功能

    if args.music_only:
        exporter = audio._AudioBatchExporter(output_dir)
        files = exporter.export_all_music(duration_sec=args.duration)
    elif args.sfx_only:
        exporter = audio._AudioBatchExporter(output_dir)
        files = exporter.export_all_sfx()
    else:
        files = audio.export_all(output_dir, music_duration=args.duration)

    # 输出汇总
    total_sfx = sum(len(v) for v in ALL_SFX_PRESETS.values())
    total_music = len(ALL_MUSIC_PATTERNS)
    print(f"\n  ✅ 导出完成!")
    print(f"     音效: {total_sfx} 个 | 音乐: {total_music} 首")
    print(f"     位置: {output_dir}\n")


if __name__ == "__main__":
    main()

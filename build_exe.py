# -*- coding: utf-8 -*-
"""打包脚本 — 生成 exe 并保持 Excel 外部配置
\n用法:
  python build_exe.py           # 完整打包 + 复制外部配置
  python build_exe.py --clean   # 清理后重新打包
"""
import os
import sys
import shutil
import subprocess
import argparse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_FILE = os.path.join(BASE_DIR, "BeeIdleRPG.spec")
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")

# 需要外放到 dist/ 的外部资源（Excel 配置 + JSON 回退模板）
EXTERNAL_RESOURCES = [
    # (源路径, dist 内相对路径)
    ("src/resources/config/game_config.xlsx",  "resources/config/game_config.xlsx"),
    ("src/resources/config/game_config.xlsx.bak", "resources/config/game_config.xlsx.bak"),
    # JSON 数据模板（外放后可作为 Excel 缺失时的回退，也可让用户直接编辑）
    ("src/resources/data",                      "resources/data"),
]


def clean():
    """清理旧构建产物"""
    for d in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  已删除: {os.path.basename(d)}/")


def build():
    """运行 PyInstaller 打包"""
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", SPEC_FILE],
        cwd=BASE_DIR,
        capture_output=False,
    )
    if result.returncode != 0:
        print("\n❌ 打包失败！请检查上方错误信息。")
        sys.exit(1)


def copy_external_resources():
    """复制外部资源到 dist 目录"""
    print("\n[3/3] 复制外部资源到 dist 目录...")
    for src, dst_rel in EXTERNAL_RESOURCES:
        src_path = os.path.join(BASE_DIR, src)
        dst_path = os.path.join(DIST_DIR, dst_rel)

        if not os.path.exists(src_path):
            print(f"  ⚠ 跳过（源不存在）: {src}")
            continue

        if os.path.isdir(src_path):
            os.makedirs(dst_path, exist_ok=True)
            for fname in os.listdir(src_path):
                s = os.path.join(src_path, fname)
                d = os.path.join(dst_path, fname)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
            print(f"  已复制目录: {dst_rel}/")
        else:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
            print(f"  已复制: {dst_rel}")


def print_summary():
    exe_path = os.path.join(DIST_DIR, "BeeIdleRPG.exe")
    size_mb = os.path.getsize(exe_path) / 1024 / 1024 if os.path.exists(exe_path) else 0
    print("\n" + "=" * 52)
    print("  ✅ 打包完成！")
    print(f"  输出目录 : {DIST_DIR}")
    print(f"  可执行文件: {exe_path}")
    print(f"  文件大小 : {size_mb:.1f} MB")
    print()
    print("  [外部配置] dist/resources/config/game_config.xlsx")
    print("    用户可直接编辑此 Excel 文件来修改游戏数据。")
    print("    删除 Excel 将自动使用内置 JSON 配置。")
    print()
    print("  [JSON 回退] dist/resources/data/*.json")
    print("    当 Excel 不存在时，程序从此目录读取 JSON 配置。")
    print("=" * 52)


def main():
    parser = argparse.ArgumentParser(description="BeeIdleRPG 打包工具")
    parser.add_argument("--clean", action="store_true", help="仅清理构建产物")
    args = parser.parse_args()

    print("=" * 52)
    print("  蜂蜜挂机 RPG — PyInstaller 打包")
    print("=" * 52)

    if args.clean:
        print("\n[清理] 删除 build/ 和 dist/...")
        clean()
        print("  完成。")
        return

    # 1. 清理旧构建
    print("\n[1/3] 清理旧构建产物...")
    clean()

    # 2. 运行 PyInstaller
    print("\n[2/3] 运行 PyInstaller 打包...")
    build()

    # 3. 复制外部资源
    copy_external_resources()

    # 4. 输出结果
    print_summary()


if __name__ == "__main__":
    main()

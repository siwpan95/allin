# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for BeeIdleRPG
# 运行时工作目录 = spec 文件所在目录

import os

# 项目根目录（spec 文件所在目录）
BASE_DIR = os.path.abspath('.')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[BASE_DIR],
    binaries=[],
    # datas: (源路径, 运行时相对路径)
    # 数据文件打包进 exe；Excel 配置外放（由 build_exe.py 复制到 dist/）
    datas=[
        # 源路径(项目内) → 运行时路径(相对于 _MEIPASS 或 exe 目录)
        # JSON 数据模板：打包进 exe，同时 build_exe.py 会外放到 dist/resources/data/
        ('src/resources/data', 'resources/data'),
    ],
    hiddenimports=[
        'pystray', 'PIL', 'PIL._imaging', 'openpyxl',
        'numpy', 'scipy', 'scipy.io', 'scipy.io.wavfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BeeIdleRPG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(BASE_DIR, 'BeeIdleRPG.ico'),   # 窗口图标
)

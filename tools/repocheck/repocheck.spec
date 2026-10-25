# -*- mode: python ; coding: utf-8 -*-
# repocheck 发行版 spec（console=False，无控制台窗口的 GUI 版）
import os

# PyInstaller 注入的 SPECPATH；直接 python 跑时回退到当前目录
try:
    _here = SPECPATH
except NameError:  # pragma: no cover
    _here = os.getcwd()

a = Analysis(
    [os.path.join(_here, 'main.py')],
    pathex=[_here],
    binaries=[],
    datas=[

    ],
    hiddenimports=[

    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch','cupy','dask','jax','jaxlib','ndonnx','sparse','sqlalchemy','matplotlib','IPython','Cython','setuptools','traitlets','jedi','pygments','yt_dlp','playwright','botocore','boto3','transformers','tokenizers','pyarrow','llvmlite','numba','scipy','sklearn','scikit-learn','imageio','imageio_ffmpeg','tensorflow','keras','moviepy','sympy','statsmodels','nltk','networkx','PyQt5','PyQt6','PySide2','PySide6','pymongo','bson','license_expression','detect_secrets','markdown_it','requirements','packaging'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='repocheck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    contents_directory='.',
)

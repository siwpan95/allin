# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="bee-idle-rpg",
    version="0.1.0",
    description="蜂蜜挂机 RPG - 零操作文字冒险",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "pystray>=0.19.0",
        "Pillow>=9.0.0",
    ],
    entry_points={
        "console_scripts": [
            "bee-rpg=main:main",
        ],
    },
)

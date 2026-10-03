# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH)
src_root = project_root / "src"

hiddenimports = [
    "PyQt5.QtSvg",
    "qrcode.image.pil",
    "websocket",
]

a = Analysis(
    [str(src_root / "app247_terminal" / "main.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=[(str(project_root / "assets"), "assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "IPython",
        "jedi",
        "nbformat",
        "notebook",
        "pytest",
        "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="app247-terminal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="app247-terminal",
)

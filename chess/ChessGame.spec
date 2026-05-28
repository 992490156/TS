# -*- mode: python ; coding: utf-8 -*-


import os
import PyInstaller.utils.win32.winutils

tk_dll_dir = 'D:/Anaconda/Library/bin'
tk_lib_dir = 'D:/Anaconda/Library/lib'

# Include Tcl/Tk DLLs
tk_binaries = [
    (os.path.join(tk_dll_dir, 'tk86t.dll'), '.'),
    (os.path.join(tk_dll_dir, 'tcl86t.dll'), '.'),
]

# Include Tcl/Tk script libraries
tk_datas = [
    (os.path.join(tk_lib_dir, 'tcl8.6'), 'tcl8.6'),
    (os.path.join(tk_lib_dir, 'tk8.6'), 'tk8.6'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=tk_binaries,
    datas=tk_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ChessGame',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

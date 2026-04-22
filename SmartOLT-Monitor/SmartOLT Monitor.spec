# smartolt_monitor_app.spec – FINAL (One-file, includes toast + icons)

import os
from PyInstaller.utils.hooks import collect_submodules

project_path = os.path.abspath(os.path.dirname(__file__))

block_cipher = None

# Hidden imports (important for win10toast_click)
hidden = collect_submodules('win10toast_click')

a = Analysis(
    ['smartolt_monitor_app.py'],
    pathex=[project_path],
    binaries=[],
    datas=[
        ('telegram_config.json', '.'),
        ('alert_soft.wav', '.'),
        ('app_icon.ico', '.'),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartOLT-Monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # GUI only
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
)

# ONE-FILE FINAL EXE
app = BUNDLE(
    coll,
    name='SmartOLT-Monitor.exe',
    icon='app_icon.ico',
)

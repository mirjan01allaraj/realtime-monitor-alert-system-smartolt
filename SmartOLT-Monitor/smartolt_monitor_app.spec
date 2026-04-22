# smartolt_monitor_app.spec
# FINAL — ONE FILE BUILD

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

project_path = os.path.abspath(".")
sys.path.insert(0, project_path)

# ---------------------------------------------------------
# 1) Collect dependencies for Flask, PIL, pystray, CTk
# ---------------------------------------------------------
hiddenimports = []
hiddenimports += collect_submodules("PIL")
hiddenimports += collect_submodules("pystray")
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("win10toast")
hiddenimports += collect_submodules("flask")
hiddenimports += collect_submodules("requests")

# ---------------------------------------------------------
# 2) Include needed files
# ---------------------------------------------------------
datas = []
datas += collect_data_files("PIL")
datas += collect_data_files("customtkinter")
datas += [
    ("telegram_config.json", "."),
    ("alert_soft.wav", "."),
    ("app_icon.ico", "."),
]

# ---------------------------------------------------------
# 3) MAIN EXE CONFIG (ONEFILE)
# ---------------------------------------------------------
a = Analysis(
    ["smartolt_monitor_app.py"],
    pathex=[project_path],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="SmartOLT-Monitor",
    debug=False,
    strip=False,
    upx=True,
    console=False,      # ❗ GUI, no console
    icon="app_icon.ico"
)

# ONE-FILE MODE
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="SmartOLT-Monitor"
)

# PyInstaller build spec — produces a single dist/DragonwildsSync.exe
# Build with:  .\.venv\Scripts\python.exe -m PyInstaller --noconfirm DragonwildsSync.spec

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[("app/assets/icon.ico", "app/assets")],
    hiddenimports=[],
    excludes=[
        "tkinter",
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtOpenGL",
        "PySide6.QtDBus",
        "PySide6.QtPdf",
        "PySide6.QtVirtualKeyboard",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DragonwildsSync",
    icon="app/assets/icon.ico",
    debug=False,
    strip=False,
    upx=False,
    console=False,            # windowed app: no terminal ever
    disable_windowed_traceback=False,
    version=None,
)

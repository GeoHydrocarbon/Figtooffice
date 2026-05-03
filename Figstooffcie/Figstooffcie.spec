# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 配置：在 Figstooffcie 目录下执行 pyinstaller Figstooffcie.spec"""
import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
spec_dir = Path(SPECPATH)

datas = list(collect_data_files("certifi"))
_bundled_xsl = spec_dir / "infra" / "equation" / "MML2OMML.XSL"
if _bundled_xsl.is_file():
    datas.append((str(_bundled_xsl), "infra/equation"))
# latex2mathml 在模块加载时读取同目录下 unimathsymbols.txt；PyInstaller 默认不会带上
_l2m_spec = importlib.util.find_spec("latex2mathml")
if _l2m_spec and _l2m_spec.origin:
    _l2m_dir = Path(_l2m_spec.origin).resolve().parent
    _uni = _l2m_dir / "unimathsymbols.txt"
    if _uni.is_file():
        datas.append((str(_uni), "latex2mathml"))
binaries = []
hiddenimports = []

# Conda 的 OpenSSL 在 Library\bin，与 DLLs\_ssl.pyd 成对；显式打入避免与系统/PySide 携带版本混用导致 _ssl 加载失败
_conda_lib_bin = spec_dir / "conda_env" / "Library" / "bin"
if _conda_lib_bin.is_dir():
    for _pattern in ("libssl-*.dll", "libcrypto-*.dll"):
        for _p in sorted(_conda_lib_bin.glob(_pattern)):
            binaries.append((str(_p), "."))

a = Analysis(
    ["main.py"],
    pathex=[str(spec_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(spec_dir / "hooks" / "rth_conda_ssl.py")],
    excludes=[
        "tkinter",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtAxContainer",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtGraphs",
        "PySide6.QtGraphsWidgets",
        "PySide6.QtHelp",
        "PySide6.QtHttpServer",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetworkAuth",
        "PySide6.QtNfc",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickTest",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialBus",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtStateMachine",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtUiTools",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtWebView",
        "PySide6.QtXml",
        "PySide6.scripts",
        "PySide6.support",
        "pandas",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Figstooffcie",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Figstooffcie",
)

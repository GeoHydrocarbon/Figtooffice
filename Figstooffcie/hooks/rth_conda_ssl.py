# PyInstaller runtime hook：确保先加载 _MEIPASS 下的 OpenSSL，避免与系统 PATH 中旧 DLL 混用
import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    root = sys._MEIPASS
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(root)
    os.environ["PATH"] = root + os.pathsep + os.environ.get("PATH", "")

from pathlib import Path
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from core.config import APP_AUTHOR, APP_NAME, build_app_paths


def _resolve_runtime_roots() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).resolve().parent
    else:
        project_root = Path(__file__).resolve().parent
    resource_root = Path(getattr(sys, "_MEIPASS", project_root))
    return project_root, resource_root


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_AUTHOR)

    project_root, resource_root = _resolve_runtime_roots()
    paths = build_app_paths(project_root, resource_root=resource_root)
    icon = QIcon(str(paths.resource_root / "docs" / "logo.ico"))
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow(paths)
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

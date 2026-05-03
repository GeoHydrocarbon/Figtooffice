from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QListWidget, QListWidgetItem


class FileDropListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(220)
        self.setToolTip("拖拽图片文件或目录到这里。")
        self._paste_handler = None

    def set_drop_hint(self, text: str) -> None:
        self.setToolTip(text)

    def set_paste_handler(self, handler) -> None:
        self._paste_handler = handler

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths: list[Path] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(Path(url.toLocalFile()))
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    def add_paths(self, paths: list[Path]) -> None:
        existing = {self.item(i).data(Qt.UserRole) for i in range(self.count())}
        for path in paths:
            value = str(path.resolve())
            if value in existing:
                continue
            item = QListWidgetItem(value)
            item.setData(Qt.UserRole, value)
            self.addItem(item)
            existing.add(value)

    def paths(self) -> list[Path]:
        out: list[Path] = []
        for i in range(self.count()):
            item = self.item(i)
            out.append(Path(item.data(Qt.UserRole)))
        return out

    def remove_selected(self) -> None:
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def keyPressEvent(self, event) -> None:
        if self._paste_handler is not None and event.matches(QKeySequence.Paste):
            self._paste_handler()
            event.accept()
            return
        super().keyPressEvent(event)

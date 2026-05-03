from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.pages.module_page import ModuleRunPage
from app.pages.settings_page import SettingsPage
from core.config import AppPaths, SettingsStore
from core.registry import ModuleRegistry
from modules.img_to_excel.module import create_module as create_excel_module
from modules.pdf_to_word.module import create_module as create_pdf_module
from modules.img_to_word.module import create_module as create_word_module


class MainWindow(QMainWindow):
    def __init__(self, paths: AppPaths) -> None:
        super().__init__()
        self.paths = paths
        self.store = SettingsStore(paths)
        self.settings = self.store.load_settings()
        self.secrets = self.store.load_secrets()
        self.registry = ModuleRegistry()
        self.registry.register(create_word_module())
        self.registry.register(create_excel_module())
        self.registry.register(create_pdf_module())

        self.setWindowTitle("Figstooffcie")
        self.resize(1200, 820)

        self.sidebar = QListWidget()
        self.stack = QStackedWidget()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("运行日志会显示在这里。")
        self.module_pages: list[tuple[object, ModuleRunPage]] = []

        for module_service in self.registry.all():
            page = ModuleRunPage(
                module_service=module_service,
                settings_supplier=self._get_runtime_settings,
                log_callback=self.append_log,
            )
            self.module_pages.append((module_service, page))
        self.settings_page = SettingsPage(
            settings=self.settings,
            secrets=self.secrets,
            store=self.store,
        )
        self.settings_page.settings_saved.connect(self._on_settings_saved)

        self._build_ui()
        self._build_menu()
        self._populate_sidebar()
        self._refresh_pages()
        self.sidebar.setCurrentRow(0)

    def _build_ui(self) -> None:
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("模块"))
        left_layout.addWidget(self.sidebar)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        for _, page in self.module_pages:
            self.stack.addWidget(page)
        self.stack.addWidget(self.settings_page)

        log_header = QWidget()
        log_header_layout = QHBoxLayout(log_header)
        log_header_layout.setContentsMargins(0, 0, 0, 0)
        log_header_layout.addWidget(QLabel("日志"))
        clear_button = QPushButton("清空日志")
        clear_button.clicked.connect(self.log_view.clear)
        log_header_layout.addStretch(1)
        log_header_layout.addWidget(clear_button)

        right_layout.addWidget(self.stack, 3)
        right_layout.addWidget(log_header)
        right_layout.addWidget(self.log_view, 2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([220, 900])

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(splitter)

        self.setCentralWidget(root)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

    def _build_menu(self) -> None:
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(lambda: self.sidebar.setCurrentRow(len(self.module_pages)))
        self.menuBar().addAction(settings_action)

    def _populate_sidebar(self) -> None:
        items = [
            (module_service.manifest.display_name, module_service.manifest.description)
            for module_service, _ in self.module_pages
        ]
        items.append(("设置", "配置 API Key、模型和默认目录"))
        for title, tooltip in items:
            item = QListWidgetItem(title)
            item.setToolTip(tooltip)
            self.sidebar.addItem(item)

    def _get_runtime_settings(self):
        return self.settings, self.secrets, self.paths

    def _refresh_pages(self) -> None:
        for _, page in self.module_pages:
            page.apply_settings(self.settings)

    def _on_settings_saved(self, settings, secrets) -> None:
        self.settings = settings
        self.secrets = secrets
        self._refresh_pages()
        self.append_log("设置已保存。")

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

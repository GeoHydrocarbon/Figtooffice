from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QPixmap
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
from core.config import APP_AUTHOR, APP_GITHUB_URL, APP_NAME, AppPaths, SettingsStore
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

        self.setWindowTitle(APP_NAME)
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
        left_layout.addWidget(self._build_brand_panel())
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
        self.statusBar().showMessage("图像与 PDF 转可编辑文档")
        github_label = QLabel(f'<a href="{APP_GITHUB_URL}">GitHub</a>')
        github_label.setTextFormat(Qt.RichText)
        github_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        github_label.setOpenExternalLinks(True)
        self.statusBar().addPermanentWidget(github_label)
        self.statusBar().addPermanentWidget(QLabel(f"Made by {APP_AUTHOR}"))
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

    def _build_brand_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        logo_label = QLabel()
        logo_label.setFixedSize(44, 44)
        logo_path = self.paths.resource_root / "docs" / "logo.png"
        if logo_path.is_file():
            pixmap = QPixmap(str(logo_path)).scaled(
                44,
                44,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            logo_label.setPixmap(pixmap)

        text_label = QLabel(
            f"<b>{APP_NAME}</b><br/><span style='color:#666666;'>Made by {APP_AUTHOR}</span>"
        )
        text_label.setTextFormat(Qt.RichText)

        layout.addWidget(logo_label, 0, Qt.AlignTop)
        layout.addWidget(text_label, 1)
        return panel

    def _build_menu(self) -> None:
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(lambda: self.sidebar.setCurrentRow(len(self.module_pages)))
        self.menuBar().addAction(settings_action)

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        self.menuBar().addAction(about_action)

        github_action = QAction("GitHub", self)
        github_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(APP_GITHUB_URL)))
        self.menuBar().addAction(github_action)

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

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"关于 {APP_NAME}",
            f"{APP_NAME}\n图像与 PDF 转可编辑文档\n\nCreated by {APP_AUTHOR}\n{APP_GITHUB_URL}",
        )

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.widgets.file_drop_list import FileDropListWidget
from app.workers import BatchWorker
from core.config import AppSettings
from core.models import ModuleRunRequest, RunContext


class ModuleRunPage(QWidget):
    def __init__(self, module_service, settings_supplier, log_callback) -> None:
        super().__init__()
        self.module_service = module_service
        self.settings_supplier = settings_supplier
        self.log_callback = log_callback
        self.worker_thread: QThread | None = None
        self.worker: BatchWorker | None = None

        self.title_label = QLabel(self.module_service.manifest.display_name)
        self.desc_label = QLabel(self.module_service.manifest.description)
        self.desc_label.setWordWrap(True)

        self.input_list = FileDropListWidget()
        self.output_dir_edit = QLineEdit()
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setMinimum(1)
        self.concurrency_spin.setMaximum(16)
        self.status_view = QTextEdit()
        self.status_view.setReadOnly(True)
        self.start_button = QPushButton("开始转换")

        self._build_ui()

    def _build_ui(self) -> None:
        header_box = QGroupBox("模块说明")
        header_layout = QVBoxLayout(header_box)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.desc_label)

        input_box = QGroupBox("输入")
        input_layout = QVBoxLayout(input_box)
        input_layout.addWidget(QLabel("支持单张、批量目录、拖拽。目录会自动展开为图片列表。"))
        input_layout.addWidget(self.input_list)

        input_buttons = QHBoxLayout()
        add_files_button = QPushButton("添加图片")
        add_dir_button = QPushButton("添加目录")
        clear_button = QPushButton("清空")
        remove_button = QPushButton("移除选中")
        add_files_button.clicked.connect(self._choose_files)
        add_dir_button.clicked.connect(self._choose_directory_input)
        clear_button.clicked.connect(self.input_list.clear)
        remove_button.clicked.connect(self.input_list.remove_selected)
        input_buttons.addWidget(add_files_button)
        input_buttons.addWidget(add_dir_button)
        input_buttons.addWidget(remove_button)
        input_buttons.addWidget(clear_button)
        input_buttons.addStretch(1)
        input_layout.addLayout(input_buttons)

        run_box = QGroupBox("运行参数")
        run_layout = QFormLayout(run_box)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit)
        output_button = QPushButton("选择目录")
        output_button.clicked.connect(self._choose_output_dir)
        output_row.addWidget(output_button)

        run_layout.addRow("输出目录", self._wrap_layout(output_row))
        run_layout.addRow("并发数", self.concurrency_spin)

        status_box = QGroupBox("当前任务")
        status_layout = QVBoxLayout(status_box)
        status_layout.addWidget(self.status_view)

        self.start_button.clicked.connect(self._start_run)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        root_layout.addWidget(header_box)
        root_layout.addWidget(input_box, 3)

        bottom_grid = QGridLayout()
        bottom_grid.addWidget(run_box, 0, 0)
        bottom_grid.addWidget(status_box, 0, 1)
        bottom_grid.setColumnStretch(0, 2)
        bottom_grid.setColumnStretch(1, 3)
        root_layout.addLayout(bottom_grid, 2)
        root_layout.addWidget(self.start_button)

    def _wrap_layout(self, layout) -> QWidget:
        wrapper = QWidget()
        wrapper.setLayout(layout)
        return wrapper

    def apply_settings(self, settings: AppSettings) -> None:
        if settings.default_output_dir:
            self.output_dir_edit.setText(settings.default_output_dir)
        self.concurrency_spin.setValue(max(1, settings.default_concurrency))

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            "",
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if paths:
            self.input_list.add_paths([Path(p) for p in paths])

    def _choose_directory_input(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择图片目录")
        if path:
            self.input_list.add_paths([Path(path)])

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def _start_run(self) -> None:
        raw_inputs = self.input_list.paths()
        if not raw_inputs:
            QMessageBox.warning(self, "输入为空", "请先添加图片或目录。")
            return

        settings, secrets, paths = self.settings_supplier()
        if not secrets.api_key.strip():
            QMessageBox.warning(self, "缺少 API Key", "请先在设置页填写 API Key。")
            return

        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            output_dir = str(raw_inputs[0].parent)

        request = ModuleRunRequest(
            input_paths=raw_inputs,
            output_dir=Path(output_dir),
            max_workers=self.concurrency_spin.value(),
            overwrite_existing=settings.overwrite_existing,
        )
        context = RunContext(
            settings=settings,
            secrets=secrets,
            paths=paths,
            log=self.log_callback,
        )

        self.status_view.clear()
        self.status_view.append("准备开始处理...")
        self.start_button.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = BatchWorker(self.module_service, request, context)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._on_worker_log)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _on_worker_log(self, message: str) -> None:
        self.status_view.append(message)
        self.log_callback(message)

    def _on_worker_progress(self, done: int, total: int) -> None:
        self.status_view.append(f"进度：{done}/{total}")

    def _on_worker_finished(self, results: list) -> None:
        ok_count = sum(1 for item in results if item.success)
        fail_count = len(results) - ok_count
        self.status_view.append(f"完成：成功 {ok_count}，失败 {fail_count}")
        self.start_button.setEnabled(True)
        self.worker = None
        self.worker_thread = None

    def _on_worker_failed(self, message: str) -> None:
        self.status_view.append(f"失败：{message}")
        QMessageBox.critical(self, "任务失败", message)
        self.start_button.setEnabled(True)
        self.worker = None
        self.worker_thread = None

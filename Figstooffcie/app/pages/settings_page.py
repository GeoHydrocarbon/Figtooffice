from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.workers import SettingsValidationWorker
from core.config import AppSettings, SecretSettings, SettingsStore


class SettingsPage(QWidget):
    settings_saved = Signal(object, object)

    def __init__(
        self,
        settings: AppSettings,
        secrets: SecretSettings,
        store: SettingsStore,
    ) -> None:
        super().__init__()
        self.store = store
        self.worker_thread: QThread | None = None
        self.worker: SettingsValidationWorker | None = None
        self.base_url_edit = QLineEdit()
        self.word_model_edit = QLineEdit()
        self.table_model_edit = QLineEdit()
        self.output_dir_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setMinimum(1)
        self.concurrency_spin.setMaximum(16)
        self.overwrite_checkbox = QCheckBox("允许覆盖同名输出文件")
        self.validation_status = QLabel("尚未验证。")
        self.validation_status.setWordWrap(True)
        self.save_button = QPushButton("保存设置")
        self.validate_button = QPushButton("验证 API Key 和模型")

        self._build_ui()
        self.load_values(settings, secrets)

    def _build_ui(self) -> None:
        form = QFormLayout()
        form.addRow("Provider Base URL", self.base_url_edit)
        form.addRow("Word 模型", self.word_model_edit)
        form.addRow("Excel 模型", self.table_model_edit)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit)
        output_button = QPushButton("选择目录")
        output_button.clicked.connect(self._choose_output_dir)
        output_row.addWidget(output_button)
        output_wrapper = QWidget()
        output_wrapper.setLayout(output_row)
        form.addRow("默认输出目录", output_wrapper)

        form.addRow("默认并发数", self.concurrency_spin)
        form.addRow("API Key", self.api_key_edit)
        form.addRow("", self.overwrite_checkbox)
        form.addRow("验证状态", self.validation_status)

        self.save_button.clicked.connect(self._save)
        self.validate_button.clicked.connect(self._validate_settings)

        button_row = QHBoxLayout()
        button_row.addWidget(self.validate_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        root.addLayout(form)
        root.addStretch(1)
        root.addLayout(button_row)

    def load_values(self, settings: AppSettings, secrets: SecretSettings) -> None:
        self.base_url_edit.setText(settings.base_url)
        self.word_model_edit.setText(settings.word_model)
        self.table_model_edit.setText(settings.table_model)
        self.output_dir_edit.setText(settings.default_output_dir)
        self.concurrency_spin.setValue(max(1, settings.default_concurrency))
        self.api_key_edit.setText(secrets.api_key)
        self.overwrite_checkbox.setChecked(settings.overwrite_existing)

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择默认输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def _collect_values(self) -> tuple[AppSettings, SecretSettings]:
        settings = AppSettings(
            base_url=self.base_url_edit.text().strip() or AppSettings().base_url,
            word_model=self.word_model_edit.text().strip() or AppSettings().word_model,
            table_model=self.table_model_edit.text().strip() or AppSettings().table_model,
            default_output_dir=self.output_dir_edit.text().strip(),
            default_concurrency=self.concurrency_spin.value(),
            overwrite_existing=self.overwrite_checkbox.isChecked(),
        )
        secrets = SecretSettings(api_key=self.api_key_edit.text().strip())
        return settings, secrets

    def _save(self) -> None:
        settings, secrets = self._collect_values()
        self.store.save_settings(settings)
        self.store.save_secrets(secrets)
        self.settings_saved.emit(settings, secrets)
        QMessageBox.information(self, "设置", "设置已保存。")

    def _validate_settings(self) -> None:
        settings, secrets = self._collect_values()
        self.validation_status.setText("验证中...")
        self.validate_button.setEnabled(False)
        self.save_button.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = SettingsValidationWorker(settings, secrets)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._on_validation_log)
        self.worker.finished.connect(self._on_validation_success)
        self.worker.failed.connect(self._on_validation_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _on_validation_log(self, message: str) -> None:
        self.validation_status.setText(message)

    def _on_validation_success(self, message: str) -> None:
        self.validation_status.setText("验证成功。")
        self._reset_validation_state()
        QMessageBox.information(self, "验证成功", message)

    def _on_validation_failed(self, message: str) -> None:
        self.validation_status.setText(f"验证失败：{message}")
        self._reset_validation_state()
        QMessageBox.warning(self, "验证失败", message)

    def _reset_validation_state(self) -> None:
        self.validate_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.worker = None
        self.worker_thread = None

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from infra.ai import build_provider
from core.task_runner import BatchTaskRunner


class BatchWorker(QObject):
    log = Signal(str)
    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, module_service, request, context) -> None:
        super().__init__()
        self.module_service = module_service
        self.request = request
        self.context = context

    @Slot()
    def run(self) -> None:
        runner = BatchTaskRunner()
        try:
            results = runner.run_batch(
                self.module_service,
                self.request,
                self.context,
                progress_callback=self.progress.emit,
                log_callback=self.log.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(results)


class SettingsValidationWorker(QObject):
    log = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, settings, secrets) -> None:
        super().__init__()
        self.settings = settings
        self.secrets = secrets

    @Slot()
    def run(self) -> None:
        try:
            provider = build_provider(self.settings, self.secrets)
            checks = [
                ("Word", self.settings.word_model.strip()),
                ("Excel", self.settings.table_model.strip()),
            ]
            validated: dict[str, str] = {}
            messages: list[str] = []

            for label, model in checks:
                if not model:
                    raise ValueError(f"{label} 模型名称为空。")
                self.log.emit(f"正在验证 {label} 模型：{model}")
                if model not in validated:
                    validated[model] = provider.validate_model(model)
                reply = validated[model]
                messages.append(f"{label} 模型可用：{model}，模型回复：{reply}")
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit("\n".join(messages))

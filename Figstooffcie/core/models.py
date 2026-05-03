from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from core.config import AppPaths, AppSettings, SecretSettings


@dataclass(frozen=True)
class ModuleManifest:
    module_id: str
    display_name: str
    description: str
    output_extension: str
    input_extensions: tuple[str, ...] = ()
    input_file_label: str = "文件"
    input_dialog_title: str = "选择文件"
    input_dialog_filter: str = "所有文件 (*)"
    input_hint: str = "支持单个文件、批量目录、拖拽。"
    accepts_clipboard_image: bool = False


@dataclass
class ModuleRunRequest:
    input_paths: list[Path]
    output_dir: Path
    max_workers: int = 1
    overwrite_existing: bool = False


@dataclass
class RunContext:
    settings: AppSettings
    secrets: SecretSettings
    paths: AppPaths
    log: Callable[[str], None]


@dataclass
class FileTaskResult:
    input_path: Path
    success: bool
    output_path: Path | None = None
    message: str = ""
    error: str = ""


class ModuleService(Protocol):
    manifest: ModuleManifest

    def expand_inputs(self, input_paths: list[Path]) -> list[Path]:
        ...

    def validate_inputs(self, input_paths: list[Path]) -> None:
        ...

    def run_single(self, input_path: Path, output_path: Path, context: RunContext) -> None:
        ...

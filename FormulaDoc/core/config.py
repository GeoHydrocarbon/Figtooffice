from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


APP_NAME = "FormulaDoc"
APP_AUTHOR = "Jorlin"
APP_GITHUB_URL = "https://github.com/GeoHydrocarbon/FormulaDoc"
LEGACY_APP_NAMES = ("Figstooffcie",)
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
SUPPORTED_PDF_EXTENSIONS = (".pdf",)


@dataclass
class AppSettings:
    provider: str = "siliconflow"
    base_url: str = "https://api.siliconflow.cn/v1"
    word_model: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    table_model: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    default_output_dir: str = ""
    default_concurrency: int = 1
    overwrite_existing: bool = False


@dataclass
class SecretSettings:
    api_key: str = ""


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    resource_root: Path
    user_data_dir: Path
    settings_file: Path
    secrets_file: Path


def build_app_paths(project_root: Path, resource_root: Path | None = None) -> AppPaths:
    resolved_resource_root = resource_root or project_root
    base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    user_data_dir = base_dir / APP_NAME
    try:
        user_data_dir.mkdir(parents=True, exist_ok=True)
        _migrate_legacy_data(base_dir, user_data_dir)
    except PermissionError:
        user_data_dir = project_root / ".localdata"
        user_data_dir.mkdir(parents=True, exist_ok=True)
    return AppPaths(
        project_root=project_root,
        resource_root=resolved_resource_root,
        user_data_dir=user_data_dir,
        settings_file=user_data_dir / "settings.json",
        secrets_file=user_data_dir / "secrets.json",
    )


def _migrate_legacy_data(base_dir: Path, user_data_dir: Path) -> None:
    for legacy_name in LEGACY_APP_NAMES:
        legacy_dir = base_dir / legacy_name
        if not legacy_dir.is_dir() or legacy_dir == user_data_dir:
            continue
        for filename in ("settings.json", "secrets.json"):
            source = legacy_dir / filename
            target = user_data_dir / filename
            if source.is_file() and not target.exists():
                shutil.copy2(source, target)
        break


class SettingsStore:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load_settings(self) -> AppSettings:
        return self._load_dataclass(self.paths.settings_file, AppSettings)

    def save_settings(self, settings: AppSettings) -> None:
        self._save_dataclass(self.paths.settings_file, settings)

    def load_secrets(self) -> SecretSettings:
        return self._load_dataclass(self.paths.secrets_file, SecretSettings)

    def save_secrets(self, secrets: SecretSettings) -> None:
        self._save_dataclass(self.paths.secrets_file, secrets)

    def _load_dataclass(self, path: Path, cls):
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return cls()
        return cls(**data)

    def _save_dataclass(self, path: Path, value) -> None:
        path.write_text(
            json.dumps(asdict(value), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

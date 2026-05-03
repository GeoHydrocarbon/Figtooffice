from __future__ import annotations

from pathlib import Path

from core.config import SUPPORTED_IMAGE_EXTENSIONS


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def expand_image_inputs(paths: list[Path]) -> list[Path]:
    return expand_supported_inputs(paths, SUPPORTED_IMAGE_EXTENSIONS)


def is_supported_extension(path: Path, extensions: tuple[str, ...] | list[str]) -> bool:
    return path.suffix.lower() in {item.lower() for item in extensions}


def expand_supported_inputs(
    paths: list[Path],
    extensions: tuple[str, ...] | list[str],
) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            for item in sorted(path.iterdir()):
                if item.is_file() and is_supported_extension(item, extensions):
                    resolved = item.resolve()
                    if resolved not in seen:
                        out.append(resolved)
                        seen.add(resolved)
            continue
        if path.is_file():
            if not is_supported_extension(path, extensions):
                continue
            if path not in seen:
                out.append(path)
                seen.add(path)
            continue
        raise FileNotFoundError(f"找不到输入路径：{path}")
    return out

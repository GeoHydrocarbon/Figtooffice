from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from generate_docx_with_equations import find_mml2omml_xsl
from markdown_to_docx import build_docx_from_markdown
from siliconflow_recognition import (
    load_yaml_config,
    openai_client_from_config,
    recognize_image_to_markdown,
)


def resolve_path(raw: str | Path | None, base_dir: Path) -> Path | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    p = Path(s)
    return p.resolve() if p.is_absolute() else (base_dir / p).resolve()


def list_images(directory: Path, extensions: list[str]) -> list[Path]:
    ext_set = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    out: list[Path] = []
    for p in sorted(directory.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in ext_set:
            out.append(p)
    return out


def merge_batch_markdown(images: list[Path], markdowns: list[str], heading_template: str) -> str:
    chunks: list[str] = []
    for path, md in zip(images, markdowns, strict=True):
        title = heading_template.format(filename=path.name)
        chunks.append(f"# {title}\n\n{md.strip()}\n")
    return "\n".join(chunks)


def derive_output_docx(
    *,
    mode: str,
    image_path: Path | None,
    image_dir: Path | None,
    output_dir: Path | None,
) -> Path:
    if mode == "single":
        assert image_path is not None
        base = output_dir if output_dir is not None else image_path.parent
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{image_path.stem}.docx"
    if mode == "batch":
        assert image_dir is not None
        base = output_dir if output_dir is not None else image_dir.parent
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{image_dir.name}.docx"
    raise ValueError(f"不支持的 mode: {mode!r}，应为 single 或 batch")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="硅基流动识图 → Markdown → 带可编辑公式的 Word（行内 $...$，块级 $$...$$ 居中）。"
    )
    p.add_argument("--config", default="config.yaml", help="YAML 配置文件路径")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--image", type=Path, help="单张图片路径（覆盖 config.io）")
    g.add_argument("--image-dir", type=Path, help="图片目录（覆盖 config.io，批量合并）")
    p.add_argument("--output", type=Path, help="输出 .docx 路径（指定则覆盖按输入名推导）")
    p.add_argument("--save-markdown", type=Path, help="将合并后的 Markdown 存到该路径")
    p.add_argument(
        "--xsl",
        help="覆盖 config 中的 MML2OMML.XSL；不传则用 config.docx.xsl_path 或自动查找",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"找不到配置文件: {cfg_path.resolve()}")

    config_dir = cfg_path.parent.resolve()
    config = load_yaml_config(cfg_path)
    client = openai_client_from_config(config)
    docx_cfg_yaml = config.get("docx") or {}
    pipe_cfg = config.get("pipeline") or {}
    io_cfg = config.get("io") or {}

    xsl_arg = args.xsl
    if xsl_arg:
        xsl_path = find_mml2omml_xsl(xsl_arg)
    else:
        xsl_yaml = docx_cfg_yaml.get("xsl_path")
        xsl_path = find_mml2omml_xsl(str(xsl_yaml)) if xsl_yaml else find_mml2omml_xsl(None)

    extensions = pipe_cfg.get("image_extensions") or [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".gif",
    ]
    heading_tpl = (pipe_cfg.get("batch_section_heading_template") or "【{filename}】").strip()

    mode: str
    image_path: Path | None = None
    image_dir: Path | None = None

    if args.image is not None:
        mode = "single"
        image_path = args.image.resolve()
    elif args.image_dir is not None:
        mode = "batch"
        image_dir = args.image_dir.resolve()
    else:
        mode = str(io_cfg.get("mode") or "single").strip().lower()
        if mode not in ("single", "batch"):
            raise ValueError('config.io.mode 须为 "single" 或 "batch"')
        if mode == "single":
            image_path = resolve_path(io_cfg.get("input_image"), config_dir)
        else:
            image_dir = resolve_path(io_cfg.get("input_dir"), config_dir)

    out_dir_cfg = resolve_path(io_cfg.get("output_dir"), config_dir)

    if mode == "single":
        if image_path is None:
            raise ValueError('单图模式请在 config.io.input_image 填写路径，或使用 --image')
        if not image_path.is_file():
            raise FileNotFoundError(f"找不到图片: {image_path}")
        md = recognize_image_to_markdown(image_path, config, client=client)
        output_docx = (
            args.output.resolve()
            if args.output is not None
            else derive_output_docx(
                mode="single",
                image_path=image_path,
                image_dir=None,
                output_dir=out_dir_cfg,
            )
        )
    else:
        if image_dir is None:
            raise ValueError('批量模式请在 config.io.input_dir 填写目录，或使用 --image-dir')
        if not image_dir.is_dir():
            raise NotADirectoryError(f"不是目录: {image_dir}")
        images = list_images(image_dir, list(extensions))
        if not images:
            raise FileNotFoundError(f"目录内未找到支持的图片: {image_dir}")
        parts = [recognize_image_to_markdown(img, config, client=client) for img in images]
        md = merge_batch_markdown(images, parts, heading_tpl)
        output_docx = (
            args.output.resolve()
            if args.output is not None
            else derive_output_docx(
                mode="batch",
                image_path=None,
                image_dir=image_dir,
                output_dir=out_dir_cfg,
            )
        )

    save_md_path: Path | None = None
    if args.save_markdown is not None:
        save_md_path = args.save_markdown.resolve()
    elif io_cfg.get("save_markdown") is True or io_cfg.get("save_json") is True:
        save_md_path = output_docx.with_suffix(".md")

    if save_md_path is not None:
        save_md_path.parent.mkdir(parents=True, exist_ok=True)
        save_md_path.write_text(md, encoding="utf-8")
        print(f"已保存 Markdown: {save_md_path}")

    build_docx_from_markdown(md, xsl_path, output_docx)
    print(f"已生成 Word: {output_docx}")


if __name__ == "__main__":
    main()

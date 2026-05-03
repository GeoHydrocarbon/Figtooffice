from __future__ import annotations

from pathlib import Path

from core.config import SUPPORTED_IMAGE_EXTENSIONS
from core.exceptions import ModuleValidationError
from core.files import expand_image_inputs, is_supported_image
from core.models import ModuleManifest, RunContext
from infra.ai import build_provider
from infra.ai.vision_provider import PromptSet
from infra.exporters.docx_exporter import export_markdown_to_docx


WORD_PROMPTS = PromptSet(
    system_prompt=(
        "你是 OCR/排版还原助手。用户上传教材或论文类截图，请用 Markdown 还原内容。\n"
        "必须遵守：\n"
        "1) 只输出 Markdown 正文，不要前言后语。\n"
        "2) 标题用 # / ## / ###。\n"
        "3) 普通段落自然分段。\n"
        "4) 行内公式使用 $...$。\n"
        "5) 独立公式使用 $$...$$ 或三行块级形式。\n"
        "6) 忠实还原图中文字、公式和顺序，不要编造内容。"
    ),
    user_prompt="请根据上图输出 Markdown。",
)


class ImageToWordService:
    manifest = ModuleManifest(
        module_id="img_to_word",
        display_name="图片转 Word",
        description="将图片识别为 Markdown，并导出为带可编辑公式的 Word 文档。",
        output_extension=".docx",
        input_extensions=SUPPORTED_IMAGE_EXTENSIONS,
        input_file_label="图片",
        input_dialog_title="选择图片",
        input_dialog_filter="图片 (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        input_hint="支持单张图片、图片目录、拖拽、剪贴板粘贴。目录会自动展开为图片列表。",
        accepts_clipboard_image=True,
    )

    def expand_inputs(self, input_paths: list[Path]) -> list[Path]:
        return expand_image_inputs(input_paths)

    def validate_inputs(self, input_paths: list[Path]) -> None:
        if not input_paths:
            raise ModuleValidationError("没有可处理的图片。")
        for path in input_paths:
            if not path.is_file():
                raise ModuleValidationError(f"不是文件：{path}")
            if not is_supported_image(path):
                raise ModuleValidationError(f"不支持的图片格式：{path.name}")

    def run_single(self, input_path: Path, output_path: Path, context: RunContext) -> None:
        provider = build_provider(context.settings, context.secrets)
        markdown = provider.recognize_markdown(
            image_path=input_path,
            prompts=WORD_PROMPTS,
            model=context.settings.word_model,
        )
        export_markdown_to_docx(markdown=markdown, output_path=output_path)

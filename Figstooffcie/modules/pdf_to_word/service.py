from __future__ import annotations

from pathlib import Path

from core.config import SUPPORTED_PDF_EXTENSIONS
from core.exceptions import ModuleValidationError
from core.files import expand_supported_inputs
from core.models import ModuleManifest, RunContext
from infra.pdf.pipeline import PdfToWordPipeline


class PdfToWordService:
    manifest = ModuleManifest(
        module_id="pdf_to_word",
        display_name="PDF 转 Word",
        description="按页分析 PDF，重点保留文字、公式和表格，忽略图片并导出为 Word。",
        output_extension=".docx",
        input_extensions=SUPPORTED_PDF_EXTENSIONS,
        input_file_label="PDF",
        input_dialog_title="选择 PDF",
        input_dialog_filter="PDF (*.pdf)",
        input_hint="支持单个 PDF、PDF 目录、拖拽。目录会自动展开为 PDF 列表。",
    )

    def expand_inputs(self, input_paths: list[Path]) -> list[Path]:
        return expand_supported_inputs(input_paths, SUPPORTED_PDF_EXTENSIONS)

    def validate_inputs(self, input_paths: list[Path]) -> None:
        if not input_paths:
            raise ModuleValidationError("没有可处理的 PDF。")
        for path in input_paths:
            if not path.is_file():
                raise ModuleValidationError(f"不是文件：{path}")
            if path.suffix.lower() not in SUPPORTED_PDF_EXTENSIONS:
                raise ModuleValidationError(f"不支持的 PDF 格式：{path.name}")

    def run_single(self, input_path: Path, output_path: Path, context: RunContext) -> None:
        pipeline = PdfToWordPipeline(context)
        pipeline.convert(pdf_path=input_path, output_path=output_path)

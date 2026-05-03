from __future__ import annotations

from pathlib import Path

from core.exceptions import ModuleValidationError
from core.files import is_supported_image
from core.models import ModuleManifest, RunContext
from infra.ai import build_provider
from infra.ai.vision_provider import PromptSet
from infra.exporters.excel_exporter import export_workbook_to_excel
from modules.img_to_excel.schemas import TableSheetData, WorkbookData


TABLE_PROMPTS = PromptSet(
    system_prompt=(
        "你是表格还原助手。请从图片中识别单个表格，并只输出 JSON。\n"
        "输出格式必须为：\n"
        "{\n"
        '  "sheet_name": "Sheet1",\n'
        '  "headers": ["列1", "列2"],\n'
        '  "rows": [["值1", "值2"], ["值3", "值4"]]\n'
        "}\n"
        "规则：\n"
        "1) 只输出 JSON，不要额外说明。\n"
        "2) 没有表头时，headers 输出空数组。\n"
        "3) 保持单元格顺序，空白单元格用空字符串。\n"
        "4) 只处理单表，不要拆成多个 sheet。"
    ),
    user_prompt="请根据上图输出单表 JSON。",
)


class ImageToExcelService:
    manifest = ModuleManifest(
        module_id="img_to_excel",
        display_name="图片转 Excel",
        description="将单表图片识别为结构化表格，并导出为 Excel 工作簿。",
        output_extension=".xlsx",
    )

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
        raw_data = provider.recognize_json(
            image_path=input_path,
            prompts=TABLE_PROMPTS,
            model=context.settings.table_model,
        )
        workbook = WorkbookData(sheets=[self._parse_table_data(raw_data)])
        export_workbook_to_excel(workbook=workbook, output_path=output_path)

    def _parse_table_data(self, data: dict) -> TableSheetData:
        sheet_name = str(data.get("sheet_name") or "Sheet1").strip() or "Sheet1"
        headers = data.get("headers") or []
        rows = data.get("rows") or []

        if not isinstance(headers, list):
            raise ModuleValidationError("模型返回的 headers 不是数组。")
        if not isinstance(rows, list):
            raise ModuleValidationError("模型返回的 rows 不是数组。")

        text_headers = [self._normalize_cell(item) for item in headers]
        text_rows: list[list[str]] = []
        width = len(text_headers)

        for row in rows:
            if not isinstance(row, list):
                raise ModuleValidationError("模型返回的某一行不是数组。")
            text_row = [self._normalize_cell(item) for item in row]
            text_rows.append(text_row)
            width = max(width, len(text_row))

        if width == 0:
            raise ModuleValidationError("没有识别到表格内容。")

        if text_headers:
            text_headers = self._pad_row(text_headers, width)
        text_rows = [self._pad_row(row, width) for row in text_rows]
        return TableSheetData(sheet_name=sheet_name, headers=text_headers, rows=text_rows)

    def _normalize_cell(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _pad_row(self, row: list[str], width: int) -> list[str]:
        if len(row) >= width:
            return row
        return row + [""] * (width - len(row))

from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from core.document_models import (
    DocumentData,
    EquationBlock,
    EquationRun,
    HeadingBlock,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
    TextRun,
)
from core.document_parsers import document_from_block_data
from core.models import RunContext
from infra.ai import build_provider
from infra.ai.vision_provider import PromptSet
from infra.exporters.docx_exporter import export_document_to_docx


VISION_PROMPTS = PromptSet(
    system_prompt=(
        "你是 PDF 页面还原助手。请根据页面图像输出结构化 JSON。\n"
        "只输出 JSON，不要额外说明。\n"
        "格式：\n"
        "{\n"
        '  "blocks": [\n'
        '    {"type":"heading","level":1,"text":"标题"},\n'
        '    {"type":"paragraph","text":"普通段落"},\n'
        '    {"type":"mixed_paragraph","parts":[{"text":"文字 "},{"latex":"a+b"}]},\n'
        '    {"type":"equation","latex":"\\\\frac{a}{b}","number":"(1)"},\n'
        '    {"type":"table","headers":["列1","列2"],"rows":[["值1","值2"]]}\n'
        "  ]\n"
        "}\n"
        "要求：\n"
        "1) 忠实保留阅读顺序。\n"
        "2) 行内公式尽量放入 mixed_paragraph.parts 的 latex。\n"
        "3) 独立公式用 equation。\n"
        "4) 表格输出为 table。\n"
        "5) 只识别文字、公式、表格，忽略图片、图表、坐标轴和图注。"
    ),
    user_prompt="请输出这个 PDF 页面对应的结构化 JSON。",
)

FORMULA_PROMPTS = PromptSet(
    system_prompt=(
        "你是数学公式 OCR 助手。请识别图片中的单个数学公式，并只输出 JSON。\n"
        "输出格式必须为：\n"
        '{ "latex": "\\\\frac{a}{b}" }\n'
        "要求：\n"
        "1) 只输出 JSON，不要解释。\n"
        "2) latex 不要包含 $ 或 $$。\n"
        "3) 如果没有公式，latex 输出空字符串。"
    ),
    user_prompt="请输出该公式的 LaTeX。",
)

MATH_MARKERS = ("=", "+", "-", "*", "/", "∑", "∫", "√", "^", "_", "{", "}", "\\")
FIGURE_CAPTION_PATTERN = re.compile(r"^\s*(图|Fig\.?)\s*\d+", re.IGNORECASE)
MATH_FONT_TOKENS = ("Symbol", "Italic", "Math", "CambriaMath")
SENTENCE_ENDINGS = ("。", "！", "？", "；", "：")


@dataclass
class PageItem:
    top: float
    left: float
    right: float
    bottom: float
    block: ParagraphBlock | TableBlock | HeadingBlock | EquationBlock
    merge_text_lines: bool = False


@dataclass
class _NativeTableItem:
    top: float
    left: float
    top_left_bottom_right: tuple[float, float, float, float]
    block: TableBlock


@dataclass
class _TextTableCandidate:
    top: float
    left: float
    right: float
    bottom: float
    bbox: tuple[float, float, float, float]
    column_centers: list[float]
    rows: list[list[str]]


class PdfToWordPipeline:
    def __init__(self, context: RunContext) -> None:
        self.context = context
        self._provider = None

    def convert(self, pdf_path: Path, output_path: Path) -> None:
        pdf = fitz.open(pdf_path)
        document = DocumentData()

        for page_index, page in enumerate(pdf):
            self.context.log(f"分析 PDF 第 {page_index + 1}/{pdf.page_count} 页：{pdf_path.name}")
            page_blocks = self._extract_page(page, page_index)
            document.blocks.extend(page_blocks.blocks)
            if page_index < pdf.page_count - 1:
                document.blocks.append(PageBreakBlock())

        export_document_to_docx(document, output_path)

    def _extract_page(self, page, page_index: int) -> DocumentData:
        mode = self._choose_page_mode(page)
        self.context.log(f"第 {page_index + 1} 页使用 {mode} 模式。")

        if mode == "native":
            native = self._extract_native_page(page)
            if native.blocks:
                return native
            self.context.log(f"第 {page_index + 1} 页原生提取为空，回退到 vision 模式。")

        return self._extract_vision_page(page)

    def _choose_page_mode(self, page) -> str:
        text = page.get_text("text").strip()
        if not text:
            return "vision"

        if self._is_scanned_page(page, text):
            return "vision"

        page_dict = page.get_text("dict")
        formula_blocks = 0
        text_blocks = 0
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            text_blocks += 1
            if self._classify_text_block(block) in ("formula", "mixed_formula"):
                formula_blocks += 1

        math_hits = sum(text.count(marker) for marker in MATH_MARKERS)
        if formula_blocks == 0:
            return "native"

        formula_ratio = formula_blocks / max(1, text_blocks)
        if formula_ratio >= 0.75 and len(text) < 240 and math_hits >= max(10, len(text) // 30):
            return "vision"
        return "native"

    def _is_scanned_page(self, page, text: str) -> bool:
        try:
            blocks = page.get_text("dict").get("blocks", [])
        except Exception:
            return False

        image_blocks = [block for block in blocks if block.get("type") == 1]
        if len(image_blocks) != 1:
            return False

        bbox = image_blocks[0].get("bbox") or (0, 0, 0, 0)
        image_area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
        page_area = max(1, page.rect.width * page.rect.height)
        return image_area / page_area > 0.7 and len(text) < 80

    def _extract_native_page(self, page) -> DocumentData:
        document = DocumentData()
        page_dict = page.get_text("dict")
        figure_regions = self._detect_figure_regions(page, page_dict)
        table_items = self._extract_table_items(page, figure_regions)
        table_bboxes = [item.top_left_bottom_right for item in table_items]

        items: list[PageItem] = [
            PageItem(
                top=item.top,
                left=item.left,
                right=item.top_left_bottom_right[2],
                bottom=item.top_left_bottom_right[3],
                block=item.block,
            )
            for item in table_items
        ]

        text_blocks = [
            block
            for block in page_dict.get("blocks", [])
            if block.get("type") == 0
        ]
        text_blocks.sort(key=lambda block: ((block.get("bbox") or (0, 0, 0, 0))[1], (block.get("bbox") or (0, 0, 0, 0))[0]))

        index = 0
        while index < len(text_blocks):
            block = text_blocks[index]
            bbox = tuple(block.get("bbox") or (0, 0, 0, 0))

            if self._overlaps_any(bbox, table_bboxes) or self._overlaps_any(bbox, figure_regions):
                index += 1
                continue

            block_text = self._text_block_to_string(block).strip()
            if not block_text:
                index += 1
                continue

            if self._is_figure_caption(block_text, bbox, figure_regions):
                index += 1
                continue

            classification = self._classify_text_block(block)
            if classification == "formula":
                formula_blocks = [block]
                formula_bbox = bbox
                next_index = index + 1
                while next_index < len(text_blocks):
                    next_block = text_blocks[next_index]
                    next_bbox = tuple(next_block.get("bbox") or (0, 0, 0, 0))
                    if self._overlaps_any(next_bbox, table_bboxes) or self._overlaps_any(next_bbox, figure_regions):
                        break
                    next_classification = self._classify_text_block(next_block)
                    if next_classification == "ignore":
                        next_index += 1
                        continue
                    if next_classification != "formula":
                        break
                    if not self._is_close_formula_block(formula_bbox, next_bbox):
                        break
                    formula_blocks.append(next_block)
                    formula_bbox = self._union_bboxes([formula_bbox, next_bbox])
                    next_index += 1

                items.append(self._build_equation_item_from_blocks(page, formula_blocks))
                index = next_index
                continue

            if classification == "mixed_formula":
                items.append(self._build_mixed_formula_item(page, block))
                index += 1
                continue

            heading = self._maybe_heading_from_text_block(block, block_text)
            if heading is not None:
                items.append(
                    PageItem(
                        top=bbox[1],
                        left=bbox[0],
                        right=bbox[2],
                        bottom=bbox[3],
                        block=heading,
                    )
                )
                index += 1
                continue

            items.append(
                PageItem(
                    top=bbox[1],
                    left=bbox[0],
                    right=bbox[2],
                    bottom=bbox[3],
                    block=ParagraphBlock(parts=[TextRun(text=block_text)]),
                    merge_text_lines=True,
                )
            )
            index += 1

        items.sort(key=lambda item: (item.top, item.left))
        document.blocks.extend(self._collapse_items_to_blocks(items))
        return document

    def _extract_vision_page(self, page) -> DocumentData:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image_bytes = pixmap.tobytes("png")
        data = self._get_provider().recognize_json_bytes(
            image_bytes=image_bytes,
            mime_type="image/png",
            prompts=VISION_PROMPTS,
            model=self.context.settings.word_model,
        )
        return document_from_block_data(data)

    def _get_provider(self):
        if self._provider is None:
            self._provider = build_provider(self.context.settings, self.context.secrets)
        return self._provider

    def _extract_table_items(self, page, figure_regions: list[tuple[float, float, float, float]]) -> list[_NativeTableItem]:
        items: list[_NativeTableItem] = []
        if hasattr(page, "find_tables"):
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    finder = page.find_tables()
            except Exception:
                finder = None

            raw_tables = getattr(finder, "tables", finder) or []
            for table in raw_tables:
                try:
                    rows = table.extract()
                except Exception:
                    continue
                normalized_rows = self._normalize_table_rows(rows)
                if not normalized_rows:
                    continue
                bbox = tuple(table.bbox)
                if self._overlaps_any(bbox, figure_regions):
                    continue
                items.append(
                    _NativeTableItem(
                        top=bbox[1],
                        left=bbox[0],
                        top_left_bottom_right=bbox,
                        block=TableBlock(rows=normalized_rows),
                    )
                )

        page_dict = page.get_text("dict")
        blocked_regions = figure_regions + [item.top_left_bottom_right for item in items]
        items.extend(self._extract_text_layout_table_items(page_dict, blocked_regions))
        items.sort(key=lambda item: (item.top, item.left))
        return items

    def _extract_text_layout_table_items(
        self,
        page_dict: dict,
        blocked_regions: list[tuple[float, float, float, float]],
    ) -> list[_NativeTableItem]:
        candidates: list[_TextTableCandidate] = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            bbox = tuple(block.get("bbox") or (0, 0, 0, 0))
            if self._overlaps_any(bbox, blocked_regions):
                continue
            candidate = self._build_text_layout_table_candidate(block)
            if candidate is not None:
                candidates.append(candidate)

        items: list[_NativeTableItem] = []
        if not candidates:
            return items

        candidates.sort(key=lambda item: (item.top, item.left))
        groups: list[list[_TextTableCandidate]] = []
        current_group: list[_TextTableCandidate] = []
        for candidate in candidates:
            if not current_group:
                current_group = [candidate]
                continue
            if self._can_merge_table_candidates(current_group[-1], candidate):
                current_group.append(candidate)
                continue
            groups.append(current_group)
            current_group = [candidate]
        if current_group:
            groups.append(current_group)

        for group in groups:
            all_rows: list[list[str]] = []
            bboxes: list[tuple[float, float, float, float]] = []
            for candidate in group:
                all_rows.extend(candidate.rows)
                bboxes.append(candidate.bbox)
            normalized_rows = self._trim_empty_table_rows(all_rows)
            if len(normalized_rows) < 2:
                continue
            headers, data_rows = self._split_table_header(normalized_rows)
            if not data_rows:
                continue
            bbox = self._union_bboxes(bboxes)
            items.append(
                _NativeTableItem(
                    top=bbox[1],
                    left=bbox[0],
                    top_left_bottom_right=bbox,
                    block=TableBlock(headers=headers, rows=data_rows),
                )
            )
        return items

    def _build_text_layout_table_candidate(self, block: dict) -> _TextTableCandidate | None:
        line_infos = self._extract_line_infos(block)
        if len(line_infos) < 4:
            return None
        if any(self._looks_like_sentence_fragment(info["text"]) for info in line_infos):
            return None
        if sum(1 for info in line_infos if info["math_font"]) >= max(2, len(line_infos) // 3):
            return None

        column_centers = self._cluster_axis_values(
            [self._bbox_center_x(info["bbox"]) for info in line_infos],
            tolerance=26,
        )
        if len(column_centers) < 3:
            return None

        rows = self._build_table_rows_from_line_infos(line_infos, column_centers)
        if not rows:
            return None

        filled_counts = [sum(1 for value in row if value) for row in rows]
        if max(filled_counts, default=0) < 3:
            return None
        structured_rows = sum(1 for count in filled_counts if count >= min(3, len(column_centers)))
        if structured_rows == 0:
            return None
        if sum(1 for row in rows for cell in row if self._looks_label_cell(cell)) == 0:
            return None

        bbox = tuple(block.get("bbox") or (0, 0, 0, 0))
        return _TextTableCandidate(
            top=bbox[1],
            left=bbox[0],
            right=bbox[2],
            bottom=bbox[3],
            bbox=bbox,
            column_centers=column_centers,
            rows=rows,
        )

    def _build_table_rows_from_line_infos(self, line_infos: list[dict], column_centers: list[float]) -> list[list[str]]:
        if not line_infos or not column_centers:
            return []

        row_groups: list[list[dict]] = []
        current_group: list[dict] = []
        current_center_y = 0.0
        for info in sorted(line_infos, key=lambda item: (self._bbox_center_y(item["bbox"]), item["bbox"][0])):
            center_y = self._bbox_center_y(info["bbox"])
            if not current_group:
                current_group = [info]
                current_center_y = center_y
                continue
            if abs(center_y - current_center_y) <= 6:
                current_group.append(info)
                current_center_y = (current_center_y * (len(current_group) - 1) + center_y) / len(current_group)
                continue
            row_groups.append(current_group)
            current_group = [info]
            current_center_y = center_y
        if current_group:
            row_groups.append(current_group)

        rows: list[list[str]] = []
        for group in row_groups:
            row = [""] * len(column_centers)
            for info in sorted(group, key=lambda item: item["bbox"][0]):
                col_index = min(
                    range(len(column_centers)),
                    key=lambda index: abs(self._bbox_center_x(info["bbox"]) - column_centers[index]),
                )
                text = info["text"].strip()
                if not text:
                    continue
                if row[col_index]:
                    row[col_index] = f"{row[col_index]} {text}".strip()
                else:
                    row[col_index] = text
            rows.append(row)
        return rows

    def _can_merge_table_candidates(self, previous: _TextTableCandidate, current: _TextTableCandidate) -> bool:
        if len(previous.column_centers) != len(current.column_centers):
            return False
        vertical_gap = current.top - previous.bottom
        if vertical_gap > 28:
            return False
        if abs(previous.left - current.left) > 28 or abs(previous.right - current.right) > 32:
            return False
        if self._column_layout_distance(previous.column_centers, current.column_centers) > 24:
            return False
        return True

    def _trim_empty_table_rows(self, rows: list[list[str]]) -> list[list[str]]:
        return [row for row in rows if any(cell.strip() for cell in row)]

    def _split_table_header(self, rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
        if len(rows) < 2:
            return [], rows

        first_row = rows[0]
        data_rows = rows[1:]
        data_density = max((self._row_numeric_density(row) for row in data_rows), default=0.0)
        if data_density >= 0.5 and self._row_numeric_density(first_row) < 0.35:
            return first_row, data_rows
        return [], rows

    def _row_numeric_density(self, row: list[str]) -> float:
        cells = [cell.strip() for cell in row if cell.strip()]
        if not cells:
            return 0.0
        numeric_cells = sum(1 for cell in cells if self._looks_numeric_cell(cell))
        return numeric_cells / len(cells)

    def _looks_numeric_cell(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if any(char in stripped for char in SENTENCE_ENDINGS):
            return False
        digit_count = sum(1 for char in stripped if char.isdigit())
        return digit_count >= max(1, len(stripped) // 3)

    def _looks_like_sentence_fragment(self, text: str) -> bool:
        stripped = text.strip()
        if len(stripped) >= 18:
            return True
        return any(marker in stripped for marker in SENTENCE_ENDINGS)

    def _looks_label_cell(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if self._has_chinese(stripped):
            return True
        alpha_count = sum(1 for char in stripped if char.isalpha())
        return alpha_count >= 2

    def _cluster_axis_values(self, values: list[float], tolerance: float) -> list[float]:
        if not values:
            return []

        clusters: list[list[float]] = []
        for value in sorted(values):
            if not clusters or abs(value - clusters[-1][-1]) > tolerance:
                clusters.append([value])
            else:
                clusters[-1].append(value)
        return [sum(cluster) / len(cluster) for cluster in clusters]

    def _column_layout_distance(self, previous: list[float], current: list[float]) -> float:
        if len(previous) != len(current) or not previous:
            return float("inf")
        distances = [abs(left - right) for left, right in zip(previous, current, strict=True)]
        return sum(distances) / len(distances)

    def _text_block_to_string(self, block: dict) -> str:
        return "".join(info["text"] for info in self._extract_line_infos(block))

    def _extract_line_infos(self, block: dict) -> list[dict]:
        line_infos: list[dict] = []
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(str(span.get("text") or "") for span in spans).strip()
            if not text:
                continue
            fonts = [str(span.get("font") or "") for span in spans]
            sizes = [float(span.get("size") or 0) for span in spans]
            line_infos.append(
                {
                    "text": text,
                    "fonts": fonts,
                    "sizes": sizes,
                    "bbox": tuple(line.get("bbox") or block.get("bbox") or (0, 0, 0, 0)),
                    "has_chinese": self._has_chinese(text),
                    "math_font": any(self._is_math_font(font) for font in fonts),
                    "avg_size": sum(sizes) / len(sizes) if sizes else 0,
                }
            )
        return line_infos

    def _classify_text_block(self, block: dict) -> str:
        line_infos = self._extract_line_infos(block)
        if not line_infos:
            return "ignore"

        formula_flags = [self._is_formula_line(info) for info in line_infos]
        formula_count = sum(1 for flag in formula_flags if flag)
        chinese_count = sum(1 for info in line_infos if info["has_chinese"])

        if formula_count and chinese_count:
            return "mixed_formula"
        if formula_count == len(line_infos) and formula_count >= 1:
            return "formula"
        return "text"

    def _is_formula_line(self, info: dict) -> bool:
        text = info["text"].strip()
        if not text or info["has_chinese"]:
            return False

        ascii_like = sum(1 for char in text if char.isascii() and not char.isspace())
        punctuation_like = sum(1 for char in text if char in "=+-*/^_()[]{}<>.,")
        digit_like = sum(1 for char in text if char.isdigit())
        short_line = len(text) <= 12

        if info["math_font"]:
            return True
        if short_line and (ascii_like + punctuation_like + digit_like) >= 1:
            return True
        if info["avg_size"] <= 9 and len(text) <= 16:
            return True
        return False

    def _build_mixed_formula_item(self, page, block: dict) -> PageItem:
        line_infos = self._extract_line_infos(block)
        parts: list[TextRun | EquationRun] = []
        text_buffer: list[str] = []
        index = 0

        while index < len(line_infos):
            info = line_infos[index]
            if not self._is_formula_line(info):
                text_buffer.append(info["text"])
                index += 1
                continue

            if text_buffer:
                parts.append(TextRun(text="".join(text_buffer)))
                text_buffer = []

            formula_infos = [info]
            next_index = index + 1
            while next_index < len(line_infos) and self._is_formula_line(line_infos[next_index]):
                formula_infos.append(line_infos[next_index])
                next_index += 1

            latex = self._recognize_formula(page, self._union_bboxes([item["bbox"] for item in formula_infos]))
            if latex:
                parts.append(EquationRun(latex=latex))
            else:
                parts.append(TextRun(text="".join(item["text"] for item in formula_infos)))
            index = next_index

        if text_buffer:
            parts.append(TextRun(text="".join(text_buffer)))

        bbox = tuple(block.get("bbox") or (0, 0, 0, 0))
        return PageItem(
            top=bbox[1],
            left=bbox[0],
            right=bbox[2],
            bottom=bbox[3],
            block=ParagraphBlock(parts=parts),
        )

    def _build_equation_item_from_blocks(self, page, blocks: list[dict]) -> PageItem:
        bboxes = [tuple(block.get("bbox") or (0, 0, 0, 0)) for block in blocks]
        bbox = self._union_bboxes(bboxes)
        latex = self._recognize_formula(page, bbox)
        if latex:
            block = EquationBlock(latex=latex)
        else:
            raw_text = "".join(self._text_block_to_string(item) for item in blocks)
            block = ParagraphBlock(parts=[TextRun(text=raw_text)])
        return PageItem(
            top=bbox[1],
            left=bbox[0],
            right=bbox[2],
            bottom=bbox[3],
            block=block,
        )

    def _recognize_formula(self, page, bbox: tuple[float, float, float, float]) -> str:
        rect = self._expand_rect(page.rect, fitz.Rect(*bbox), margin=8)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=rect, alpha=False)
        data = self._get_provider().recognize_json_bytes(
            image_bytes=pixmap.tobytes("png"),
            mime_type="image/png",
            prompts=FORMULA_PROMPTS,
            model=self.context.settings.word_model,
        )
        latex = str(data.get("latex") or "").strip()
        latex = latex.strip()
        if latex.startswith("$$") and latex.endswith("$$"):
            latex = latex[2:-2].strip()
        latex = latex.strip("$").strip()
        return latex

    def _collapse_items_to_blocks(self, items: list[PageItem]) -> list:
        if not items:
            return []

        text_lefts = [item.left for item in items if item.merge_text_lines]
        base_left = min(text_lefts) if text_lefts else 0

        blocks: list = []
        line_group: list[PageItem] = []
        for item in items:
            if not item.merge_text_lines:
                if line_group:
                    blocks.append(self._merge_line_group(line_group))
                    line_group = []
                blocks.append(item.block)
                continue

            if not line_group:
                line_group = [item]
                continue

            if self._should_start_new_paragraph(line_group[-1], item, base_left):
                blocks.append(self._merge_line_group(line_group))
                line_group = [item]
            else:
                line_group.append(item)

        if line_group:
            blocks.append(self._merge_line_group(line_group))
        return blocks

    def _should_start_new_paragraph(self, previous: PageItem, current: PageItem, base_left: float) -> bool:
        gap = current.top - previous.bottom
        prev_text = self._text_from_paragraph(previous.block)
        current_text = self._text_from_paragraph(current.block)

        if gap > 18:
            return True
        if current.left >= base_left + 16 and prev_text.endswith(("。", "！", "？", "；", "：", ":")):
            return True
        if current_text.startswith(("1）", "2）", "3）", "4）", "5）", "1.", "2.", "3.")):
            return True
        return False

    def _merge_line_group(self, items: list[PageItem]) -> ParagraphBlock:
        text = ""
        for item in items:
            chunk = self._text_from_paragraph(item.block).strip()
            if not chunk:
                continue
            if not text:
                text = chunk
                continue
            if self._needs_space_between(text[-1], chunk[0]):
                text += " " + chunk
            else:
                text += chunk
        return ParagraphBlock(parts=[TextRun(text=text)])

    def _text_from_paragraph(self, block: ParagraphBlock) -> str:
        return "".join(part.text for part in block.parts if isinstance(part, TextRun))

    def _needs_space_between(self, left_char: str, right_char: str) -> bool:
        return left_char.isascii() and right_char.isascii() and left_char.isalnum() and right_char.isalnum()

    def _maybe_heading_from_text_block(self, block: dict, text: str) -> HeadingBlock | None:
        font_sizes = [
            float(span.get("size") or 0)
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        ]
        if not font_sizes:
            return None
        if max(font_sizes) >= 16 and len(text) <= 80:
            return HeadingBlock(text=text, level=1)
        if re.match(r"^\d+[、.]\s*", text):
            return HeadingBlock(text=text, level=2)
        return None

    def _detect_figure_regions(self, page, page_dict: dict) -> list[tuple[float, float, float, float]]:
        regions: list[tuple[float, float, float, float]] = []

        for block in page_dict.get("blocks", []):
            if block.get("type") != 1:
                continue
            bbox = tuple(block.get("bbox") or (0, 0, 0, 0))
            if self._bbox_area(bbox) >= 5000:
                regions.append(bbox)

        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        drawing_rects: list[tuple[float, float, float, float]] = []
        for drawing in drawings:
            rect = drawing.get("rect")
            if rect is None:
                continue
            bbox = tuple(rect)
            if self._bbox_area(bbox) < 20:
                continue
            drawing_rects.append(bbox)

        for bbox in self._merge_bboxes(drawing_rects, gap=4):
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width >= 80 and height >= 50 and self._bbox_area(bbox) >= 5000:
                regions.append(bbox)

        return self._merge_bboxes(regions, gap=8)

    def _is_figure_caption(
        self,
        text: str,
        bbox: tuple[float, float, float, float],
        figure_regions: list[tuple[float, float, float, float]],
    ) -> bool:
        if not FIGURE_CAPTION_PATTERN.match(text):
            return False
        for region in figure_regions:
            vertical_gap = bbox[1] - region[3]
            horizontal_overlap = min(bbox[2], region[2]) - max(bbox[0], region[0])
            if -8 <= vertical_gap <= 24 and horizontal_overlap > 0:
                return True
        return False

    def _is_close_formula_block(
        self,
        previous_bbox: tuple[float, float, float, float],
        current_bbox: tuple[float, float, float, float],
    ) -> bool:
        vertical_overlap = min(previous_bbox[3], current_bbox[3]) - max(previous_bbox[1], current_bbox[1])
        horizontal_overlap = min(previous_bbox[2], current_bbox[2]) - max(previous_bbox[0], current_bbox[0])
        vertical_gap = max(0.0, current_bbox[1] - previous_bbox[3], previous_bbox[1] - current_bbox[3])
        horizontal_gap = max(0.0, current_bbox[0] - previous_bbox[2], previous_bbox[0] - current_bbox[2])

        same_line = vertical_overlap >= -2 and horizontal_gap <= 60
        stacked = horizontal_overlap >= -12 and vertical_gap <= 10
        return same_line or stacked

    def _overlaps_any(self, bbox: tuple[float, float, float, float], others: list[tuple[float, float, float, float]]) -> bool:
        for other in others:
            if self._bbox_overlap(bbox, other):
                return True
        return False

    def _bbox_overlap(self, a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def _bbox_area(self, bbox: tuple[float, float, float, float]) -> float:
        return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])

    def _bbox_center_x(self, bbox: tuple[float, float, float, float]) -> float:
        return (bbox[0] + bbox[2]) / 2

    def _bbox_center_y(self, bbox: tuple[float, float, float, float]) -> float:
        return (bbox[1] + bbox[3]) / 2

    def _union_bboxes(self, bboxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
        left = min(bbox[0] for bbox in bboxes)
        top = min(bbox[1] for bbox in bboxes)
        right = max(bbox[2] for bbox in bboxes)
        bottom = max(bbox[3] for bbox in bboxes)
        return (left, top, right, bottom)

    def _merge_bboxes(self, bboxes: list[tuple[float, float, float, float]], gap: float) -> list[tuple[float, float, float, float]]:
        if not bboxes:
            return []

        merged: list[tuple[float, float, float, float]] = []
        for bbox in sorted(bboxes, key=lambda item: (item[1], item[0])):
            expanded = (bbox[0] - gap, bbox[1] - gap, bbox[2] + gap, bbox[3] + gap)
            updated = False
            for index, existing in enumerate(merged):
                if self._bbox_overlap(expanded, existing):
                    merged[index] = self._union_bboxes([existing, bbox])
                    updated = True
                    break
            if not updated:
                merged.append(bbox)

        changed = True
        while changed:
            changed = False
            result: list[tuple[float, float, float, float]] = []
            for bbox in merged:
                for index, existing in enumerate(result):
                    expanded = (bbox[0] - gap, bbox[1] - gap, bbox[2] + gap, bbox[3] + gap)
                    if self._bbox_overlap(expanded, existing):
                        result[index] = self._union_bboxes([existing, bbox])
                        changed = True
                        break
                else:
                    result.append(bbox)
            merged = result
        return merged

    def _expand_rect(self, page_rect, rect: fitz.Rect, margin: float) -> fitz.Rect:
        return fitz.Rect(
            max(page_rect.x0, rect.x0 - margin),
            max(page_rect.y0, rect.y0 - margin),
            min(page_rect.x1, rect.x1 + margin),
            min(page_rect.y1, rect.y1 + margin),
        )

    def _has_chinese(self, text: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _is_math_font(self, font_name: str) -> bool:
        return any(token.lower() in font_name.lower() for token in MATH_FONT_TOKENS)

    def _normalize_table_rows(self, rows) -> list[list[str]]:
        if not isinstance(rows, list):
            return []
        normalized: list[list[str]] = []
        width = 0
        for row in rows:
            if not isinstance(row, list):
                continue
            text_row = ["" if cell is None else str(cell).strip() for cell in row]
            normalized.append(text_row)
            width = max(width, len(text_row))
        if width == 0:
            return []
        return [row + [""] * (width - len(row)) for row in normalized]

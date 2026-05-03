from __future__ import annotations

import re
from typing import Any

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


INLINE_MATH = re.compile(r"\$(?!\$)(.+?)\$(?!\$)", re.DOTALL)
HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+)$")


def text_to_paragraph_parts(text: str) -> list[TextRun | EquationRun]:
    parts: list[TextRun | EquationRun] = []
    pos = 0
    for match in INLINE_MATH.finditer(text):
        if match.start() > pos:
            chunk = text[pos : match.start()]
            if chunk:
                parts.append(TextRun(text=chunk))
        latex = match.group(1).strip()
        if latex:
            parts.append(EquationRun(latex=latex))
        pos = match.end()
    if pos < len(text):
        tail = text[pos:]
        if tail:
            parts.append(TextRun(text=tail))
    if not parts:
        parts.append(TextRun(text=text))
    return parts


def paragraph_from_text(text: str) -> ParagraphBlock:
    return ParagraphBlock(parts=text_to_paragraph_parts(text))


def document_from_markdown(markdown: str) -> DocumentData:
    document = DocumentData()
    for kind, payload in iter_markdown_events(markdown):
        if kind == "heading":
            level, text = payload
            document.blocks.append(HeadingBlock(text=text, level=level))
        elif kind == "paragraph":
            document.blocks.append(paragraph_from_text(payload))
        elif kind == "display":
            latex = payload.strip()
            if latex:
                document.blocks.append(EquationBlock(latex=latex))
    return document


def document_from_block_data(data: dict[str, Any]) -> DocumentData:
    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError('模型返回的 JSON 顶层缺少 "blocks" 数组。')

    document = DocumentData()
    for index, raw_block in enumerate(blocks):
        if not isinstance(raw_block, dict):
            raise ValueError(f"blocks[{index}] 不是对象。")

        block_type = str(raw_block.get("type") or "").strip()
        if block_type == "heading":
            text = str(raw_block.get("text") or "").strip()
            if not text:
                continue
            level = int(raw_block.get("level") or 1)
            document.blocks.append(HeadingBlock(text=text, level=max(1, min(level, 6))))
        elif block_type == "paragraph":
            text = str(raw_block.get("text") or "").strip()
            if not text:
                continue
            document.blocks.append(paragraph_from_text(text))
        elif block_type == "mixed_paragraph":
            document.blocks.append(_parse_mixed_paragraph(raw_block, index))
        elif block_type == "equation":
            latex = str(raw_block.get("latex") or "").strip()
            if not latex:
                continue
            number = str(raw_block.get("number") or "").strip() or None
            document.blocks.append(EquationBlock(latex=latex, number=number))
        elif block_type == "table":
            document.blocks.append(_parse_table_block(raw_block, index))
        elif block_type == "page_break":
            document.blocks.append(PageBreakBlock())
        else:
            raise ValueError(f"blocks[{index}] 的 type 不支持：{block_type!r}")
    return document


def iter_markdown_events(markdown: str):
    lines = markdown.splitlines()
    index = 0
    total = len(lines)
    while index < total:
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue

        heading_match = HEADING_LINE.match(stripped)
        if heading_match:
            yield "heading", (len(heading_match.group(1)), heading_match.group(2).strip())
            index += 1
            continue

        if stripped.startswith("$$"):
            if stripped.endswith("$$") and stripped.count("$$") == 2 and len(stripped) >= 6:
                yield "display", stripped[2:-2].strip()
                index += 1
                continue

            inner: list[str] = []
            if stripped != "$$":
                remainder = stripped[2:].strip()
                if remainder.endswith("$$"):
                    yield "display", remainder[:-2].strip()
                    index += 1
                    continue
                inner.append(remainder)
            index += 1
            while index < total:
                line = lines[index]
                candidate = line.strip()
                if candidate.endswith("$$"):
                    prefix = line.rsplit("$$", 1)[0]
                    if prefix.strip():
                        inner.append(prefix.rstrip())
                    index += 1
                    break
                inner.append(line)
                index += 1
            else:
                raise ValueError("存在未闭合的块级公式。")
            yield "display", "\n".join(inner).strip()
            continue

        buffer = [lines[index]]
        index += 1
        while index < total:
            line = lines[index]
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#") or stripped_line.startswith("$$"):
                break
            buffer.append(line)
            index += 1
        paragraph = "\n".join(buffer).strip()
        if paragraph:
            yield "paragraph", paragraph


def _parse_mixed_paragraph(raw_block: dict[str, Any], index: int) -> ParagraphBlock:
    raw_parts = raw_block.get("parts")
    if not isinstance(raw_parts, list):
        raise ValueError(f"blocks[{index}] 的 mixed_paragraph 缺少 parts 数组。")

    parts: list[TextRun | EquationRun] = []
    for part_index, part in enumerate(raw_parts):
        if not isinstance(part, dict):
            raise ValueError(f"blocks[{index}].parts[{part_index}] 不是对象。")
        if "text" in part:
            text = str(part.get("text") or "")
            if text:
                parts.append(TextRun(text=text))
            continue
        if "latex" in part:
            latex = str(part.get("latex") or "").strip()
            if latex:
                parts.append(EquationRun(latex=latex))
            continue
        raise ValueError(f"blocks[{index}].parts[{part_index}] 既没有 text，也没有 latex。")
    return ParagraphBlock(parts=parts)


def _parse_table_block(raw_block: dict[str, Any], index: int) -> TableBlock:
    headers = raw_block.get("headers") or []
    rows = raw_block.get("rows") or []

    if not isinstance(headers, list):
        raise ValueError(f"blocks[{index}] 的 table.headers 不是数组。")
    if not isinstance(rows, list):
        raise ValueError(f"blocks[{index}] 的 table.rows 不是数组。")

    text_headers = ["" if item is None else str(item).strip() for item in headers]
    text_rows: list[list[str]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise ValueError(f"blocks[{index}].rows[{row_index}] 不是数组。")
        text_rows.append(["" if item is None else str(item).strip() for item in row])

    return TableBlock(headers=text_headers, rows=text_rows)

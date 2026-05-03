from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextRun:
    text: str


@dataclass
class EquationRun:
    latex: str


@dataclass
class ParagraphBlock:
    parts: list[TextRun | EquationRun] = field(default_factory=list)


@dataclass
class HeadingBlock:
    text: str
    level: int = 1


@dataclass
class EquationBlock:
    latex: str
    number: str | None = None


@dataclass
class TableBlock:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class ImageBlock:
    image_bytes: bytes
    filename: str = "image.png"
    width_cm: float | None = None
    caption: str = ""


@dataclass
class PageBreakBlock:
    pass


@dataclass
class DocumentData:
    blocks: list[
        HeadingBlock
        | ParagraphBlock
        | EquationBlock
        | TableBlock
        | ImageBlock
        | PageBreakBlock
    ] = field(default_factory=list)

from dataclasses import dataclass, field


@dataclass
class TableSheetData:
    sheet_name: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class WorkbookData:
    sheets: list[TableSheetData] = field(default_factory=list)

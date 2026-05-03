from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class PromptSet:
    system_prompt: str
    user_prompt: str


class VisionProvider(Protocol):
    def recognize_markdown(self, image_path: Path, prompts: PromptSet, model: str) -> str:
        ...

    def recognize_json(self, image_path: Path, prompts: PromptSet, model: str) -> dict[str, Any]:
        ...


def strip_markdown_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_balanced_object(text: str, start: int) -> str:
    if start < 0 or start >= len(text) or text[start] != "{":
        raise ValueError("起始位置不是 JSON 对象。")
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue
        if char in "\"'":
            in_string = True
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("JSON 花括号不平衡。")


def parse_model_json(text: str) -> dict[str, Any]:
    content = strip_markdown_code_fence(text)
    content = content.strip()
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r"\{", content):
        try:
            raw = extract_balanced_object(content, match.start())
        except ValueError:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    preview = content if len(content) <= 1000 else f"{content[:1000]}..."
    raise ValueError(f"无法解析模型返回的 JSON。原文节选：\n{preview}")

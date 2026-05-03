from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

ALLOWED_BLOCK_TYPES = frozenset({"heading", "paragraph", "mixed_paragraph", "equation"})


def load_yaml_config(path: Path) -> dict[str, Any]:
    import yaml

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误（应为映射）: {path}")
    return data


def openai_client_from_config(config: dict[str, Any]) -> OpenAI:
    sf = config.get("siliconflow") or {}
    base_url = (sf.get("base_url") or "https://api.siliconflow.cn/v1").rstrip("/")
    return OpenAI(api_key=resolve_api_key(config), base_url=base_url)


def resolve_api_key(cfg: dict[str, Any]) -> str:
    import os

    sf = cfg.get("siliconflow") or {}
    key = (sf.get("api_key") or "").strip()
    if key:
        return key
    env_name = (sf.get("api_key_env") or "SILICONFLOW_API_KEY").strip() or "SILICONFLOW_API_KEY"
    key = (os.environ.get(env_name) or "").strip()
    if not key:
        raise ValueError(
            f"未配置 API Key：请在 config.yaml 的 siliconflow.api_key 填写，"
            f"或设置环境变量 {env_name}"
        )
    return key


def image_path_to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        suf = path.suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }.get(suf, "application/octet-stream")
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def strip_markdown_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if not lines:
        return text
    # 去掉起始 ``` 或 ```json
    lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_balanced_object(text: str, start: int) -> str:
    """从 text[start] 处的 '{' 起截取与之平衡的最外层 JSON 对象子串。"""
    if start < 0 or start >= len(text) or text[start] != "{":
        raise ValueError("extract_balanced_object: start 必须指向 '{'")
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
                quote = ""
            continue
        if ch in "\"'":
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("模型输出中 JSON 花括号不平衡")


def parse_model_json(text: str) -> dict[str, Any]:
    """解析模型输出为 dict。优先匹配含 \"blocks\" 的 JSON，避免误把前文里无效的小括号段当成主 JSON。"""
    t = strip_markdown_code_fence(text).strip()
    errors: list[str] = []

    def _try_load(raw: str) -> dict[str, Any] | None:
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError as e:
            snippet = raw.strip()
            if len(snippet) > 400:
                snippet = snippet[:400] + "..."
            errors.append(f"{e}; 片段: {snippet!r}")
            return None

    # 1) 整体就是单个 JSON 对象
    if t.startswith("{") and t.endswith("}"):
        data = _try_load(t)
        if data is not None:
            return data

    # 2) 优先：包含 "blocks" 键的对象（允许 { 与 "blocks" 之间有空白）
    for m in re.finditer(r'\{\s*"blocks"\s*:', t):
        try:
            raw = extract_balanced_object(t, m.start())
        except ValueError:
            continue
        data = _try_load(raw)
        if data is not None:
            return data

    # 3) 回退：第一个 '{' 起的平衡子串（旧逻辑，易误匹配模型胡写的 {xxx}）
    start = t.find("{")
    if start != -1:
        try:
            raw = extract_balanced_object(t, start)
            data = _try_load(raw)
            if data is not None:
                return data
        except ValueError:
            pass

    hint = (
        "无法从模型回复中解析出合法 JSON 对象。常见原因：\n"
        "1) 模型未按约定只输出 JSON（或夹杂说明文字）；\n"
        "2) max_tokens 过小导致 JSON 被截断；\n"
        "3) 模型输出了非 JSON 片段（例如 `{[53]}` 这类无效内容）。\n"
        "建议：增大 config 中 siliconflow.max_tokens，收紧 prompts.system，或更换识图模型。"
    )
    preview = t if len(t) <= 4000 else t[:4000] + "\n... (已截断)"
    tail = "\n".join(errors[-5:]) if errors else "(无成功尝试)"
    raise ValueError(f"{hint}\n---模型原文（节选）---\n{preview}\n---解析尝试---\n{tail}")


def validate_blocks_config(data: dict[str, Any]) -> None:
    if "blocks" not in data:
        raise ValueError('JSON 顶层缺少 "blocks" 数组')
    blocks = data["blocks"]
    if not isinstance(blocks, list):
        raise ValueError('"blocks" 必须是数组')
    for idx, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise ValueError(f"blocks[{idx}] 必须是对象")
        btype = block.get("type")
        if btype not in ALLOWED_BLOCK_TYPES:
            raise ValueError(f"blocks[{idx}] 不支持的 type: {btype!r}")
        if btype in ("heading", "paragraph"):
            if "text" not in block or not isinstance(block["text"], str):
                raise ValueError(f"blocks[{idx}] ({btype}) 需要字符串字段 text")
        elif btype == "mixed_paragraph":
            parts = block.get("parts")
            if not isinstance(parts, list) or not parts:
                raise ValueError(f"blocks[{idx}] (mixed_paragraph) 需要非空 parts 数组")
            for j, part in enumerate(parts):
                if not isinstance(part, dict):
                    raise ValueError(f"blocks[{idx}].parts[{j}] 必须是对象")
                if "text" in part and isinstance(part["text"], str):
                    continue
                if "latex" in part and isinstance(part["latex"], str):
                    continue
                raise ValueError(f"blocks[{idx}].parts[{j}] 须含 text 或 latex 字符串")
        elif btype == "equation":
            for key in ("latex", "number"):
                if key not in block or not isinstance(block[key], str):
                    raise ValueError(f"blocks[{idx}] (equation) 需要字符串字段 latex 与 number")


def _call_vision_chat_raw(
    image_path: Path,
    config: dict[str, Any],
    *,
    client: OpenAI | None = None,
) -> str:
    """调用硅基流动多模态 chat，返回助手文本（不做 JSON 解析）。"""
    sf = config.get("siliconflow") or {}
    base_url = (sf.get("base_url") or "https://api.siliconflow.cn/v1").rstrip("/")
    model = (sf.get("vision_model") or "").strip() or (sf.get("model") or "").strip()
    if not model:
        raise ValueError("config.yaml 中 siliconflow.model（或 vision_model）不能为空")

    api_key = resolve_api_key(config)
    if client is None:
        client = OpenAI(api_key=api_key, base_url=base_url)

    prompts = config.get("prompts") or {}
    system_prompt = (prompts.get("system") or "").strip()
    user_prompt = (prompts.get("user") or "请根据上图提取内容。").strip()

    detail = (sf.get("image_detail") or "high").strip()
    max_tokens = int(sf.get("max_tokens") or 2048)
    temperature = float(sf.get("temperature") if sf.get("temperature") is not None else 0.2)

    data_url = image_path_to_data_url(image_path)
    user_content: list[dict[str, Any]] = [
        {
            "type": "image_url",
            "image_url": {"url": data_url, "detail": detail},
        },
        {"type": "text", "text": user_prompt},
    ]
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if sf.get("enable_thinking") is True:
        kwargs["extra_body"] = {"enable_thinking": True}
    if sf.get("response_format_json_object") is True:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        raise ValueError("模型返回空内容")
    return text


def recognize_image_to_markdown(
    image_path: Path,
    config: dict[str, Any],
    *,
    client: OpenAI | None = None,
) -> str:
    """识图并返回 Markdown 正文（若模型用 ``` 围栏包裹，会去掉外层围栏）。"""
    raw = _call_vision_chat_raw(image_path, config, client=client)
    return strip_markdown_code_fence(raw).strip()


def recognize_image_to_blocks(
    image_path: Path,
    config: dict[str, Any],
    *,
    client: OpenAI | None = None,
) -> dict[str, Any]:
    """调用硅基流动多模态接口，解析 JSON，返回 { \"blocks\": [...] }（供旧版 JSON 管线使用）。"""
    text = _call_vision_chat_raw(image_path, config, client=client)
    data = parse_model_json(text)
    validate_blocks_config(data)
    return data

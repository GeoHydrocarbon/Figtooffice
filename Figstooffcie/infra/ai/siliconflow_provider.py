from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from openai import OpenAI

from infra.ai.vision_provider import PromptSet, parse_model_json, strip_markdown_code_fence

VALIDATION_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn9M7wAAAAASUVORK5CYII="
)


class SiliconFlowVisionProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        image_detail: str = "high",
    ) -> None:
        if not api_key.strip():
            raise ValueError("API Key 为空，请先在设置页填写。")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.image_detail = image_detail
        self.client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))

    def recognize_markdown(self, image_path: Path, prompts: PromptSet, model: str) -> str:
        text = self._call_model(image_path=image_path, prompts=prompts, model=model)
        return strip_markdown_code_fence(text).strip()

    def recognize_json(self, image_path: Path, prompts: PromptSet, model: str) -> dict[str, Any]:
        text = self._call_model(image_path=image_path, prompts=prompts, model=model)
        return parse_model_json(text)

    def recognize_json_bytes(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompts: PromptSet,
        model: str,
    ) -> dict[str, Any]:
        data_url = self._bytes_to_data_url(image_bytes, mime_type)
        text = self._call_model_with_data_url(data_url=data_url, prompts=prompts, model=model)
        return parse_model_json(text)

    def validate_model(self, model: str) -> str:
        if not model.strip():
            raise ValueError("模型名称为空，请先填写模型名称。")

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "你是接口可用性验证助手。只回复 OK。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": VALIDATION_IMAGE_DATA_URL, "detail": "low"},
                    },
                    {"type": "text", "text": "请只回复 OK。"},
                ],
            },
        ]
        return self._create_completion(
            model=model,
            messages=messages,
            max_tokens=32,
            temperature=0,
        )

    def _call_model(self, *, image_path: Path, prompts: PromptSet, model: str) -> str:
        if not model.strip():
            raise ValueError("模型名称为空，请先在设置页配置模型。")

        data_url = self._image_to_data_url(image_path)
        return self._call_model_with_data_url(data_url=data_url, prompts=prompts, model=model)

    def _call_model_with_data_url(
        self,
        *,
        data_url: str,
        prompts: PromptSet,
        model: str,
    ) -> str:
        messages: list[dict[str, Any]] = []
        if prompts.system_prompt.strip():
            messages.append({"role": "system", "content": prompts.system_prompt.strip()})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": self.image_detail},
                    },
                    {"type": "text", "text": prompts.user_prompt.strip()},
                ],
            }
        )
        return self._create_completion(
            model=model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

    def _create_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = self.client.chat.completions.create(
            model=model.strip(),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("模型返回了空内容。")
        return text

    def _image_to_data_url(self, path: Path) -> str:
        mime, _ = mimetypes.guess_type(path.name)
        if not mime:
            mime = "application/octet-stream"
        raw = path.read_bytes()
        return self._bytes_to_data_url(raw, mime)

    def _bytes_to_data_url(self, image_bytes: bytes, mime_type: str) -> str:
        encoded = base64.standard_b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

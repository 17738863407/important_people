from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Sequence

from crawler_core.deepseek_client import (
    parse_json_object,
    read_environment_value,
    resolve_deepseek_api_key,
    resolve_deepseek_base_url,
    sha256_text,
)


DEFAULT_DEEPSEEK_VISION_MODEL = "deepseek-v4-flash-vision-exp"


@dataclass(frozen=True)
class DeepSeekVisionResult:
    """记录一次不含密钥的DeepSeek视觉JSON调用结果。"""

    payload: dict[str, Any]
    raw_text: str
    model: str
    base_url: str
    prompt_hash: str
    input_hash: str
    elapsed_seconds: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def resolve_deepseek_vision_model() -> str:
    """读取DeepSeek视觉模型ID，默认使用官方实验视觉模型。"""
    return (
        read_environment_value("DEEPSEEK_FLASH_VISION_MODEL")
        or read_environment_value("DEEPSEEK_VISION_MODEL")
        or DEFAULT_DEEPSEEK_VISION_MODEL
    )


def resolve_deepseek_vision_detail() -> str:
    """读取图片细节级别并限制为官方支持的取值。"""
    detail = read_environment_value("DEEPSEEK_VISION_DETAIL").strip().lower() or "original"
    if detail not in {"low", "high", "original", "auto"}:
        raise ValueError(f"DEEPSEEK_VISION_DETAIL取值无效：{detail}")
    return detail


def resolve_deepseek_vision_max_tokens() -> int:
    """读取视觉JSON最大输出Token数，并限制为正整数。"""
    raw_value = read_environment_value("DEEPSEEK_VISION_MAX_TOKENS") or "32768"
    try:
        max_tokens = int(raw_value)
    except ValueError as error:
        raise ValueError(f"DEEPSEEK_VISION_MAX_TOKENS取值无效：{raw_value}") from error
    if max_tokens <= 0:
        raise ValueError("DEEPSEEK_VISION_MAX_TOKENS必须为正整数")
    return max_tokens


def build_image_data_url(image_bytes: bytes, content_type: str) -> str:
    """把图片转换为DeepSeek OpenAI兼容接口接受的data URL。"""
    media_type = str(content_type or "image/png").split(";", 1)[0].strip().lower()
    if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        media_type = "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def hash_images(images: Sequence[tuple[bytes, str]]) -> str:
    """按输入顺序计算多张图片的联合SHA-256。"""
    digest = hashlib.sha256()
    for image_bytes, content_type in images:
        digest.update(str(content_type or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(image_bytes)
        digest.update(b"\0")
    return digest.hexdigest()


def parse_vision_json_object(raw_text: str) -> dict[str, Any]:
    """解析视觉JSON；超长响应仅保守回收其中完整的行对象。"""
    try:
        return parse_json_object(raw_text)
    except (RuntimeError, json.JSONDecodeError) as original_error:
        text = str(raw_text or "").strip()
        decoder = json.JSONDecoder()
        transcription = ""
        transcription_match = re.search(r'"transcription"\s*:\s*', text)
        if transcription_match:
            try:
                value, _ = decoder.raw_decode(text, transcription_match.end())
                transcription = str(value or "")
            except json.JSONDecodeError:
                transcription = ""

        rows_match = re.search(r'"rows"\s*:\s*\[', text)
        rows: list[dict[str, Any]] = []
        if rows_match:
            index = rows_match.end()
            while index < len(text):
                while index < len(text) and (text[index].isspace() or text[index] == ","):
                    index += 1
                if index >= len(text) or text[index] == "]":
                    break
                if text[index] != "{":
                    next_row = re.search(r'\{\s*"source_order"\s*:', text[index:])
                    if not next_row:
                        break
                    index += next_row.start()
                try:
                    value, next_index = decoder.raw_decode(text, index)
                except json.JSONDecodeError:
                    next_row = re.search(r'\{\s*"source_order"\s*:', text[index + 1 :])
                    if not next_row:
                        break
                    index += next_row.start() + 1
                    continue
                if isinstance(value, dict):
                    rows.append(value)
                index = next_index

        if not transcription or not rows:
            raise original_error
        return {
            "transcription": transcription,
            "rows": rows,
            "json_recovered": True,
            "json_recovery_reason": str(original_error),
        }


def call_deepseek_vision_json(
    images: Sequence[tuple[bytes, str]],
    prompt: str,
    project_dir: Path,
    timeout_seconds: int,
) -> DeepSeekVisionResult:
    """调用DeepSeek V4 Flash视觉模型并返回严格JSON及审计元数据。"""
    normalized_images = [
        (bytes(image_bytes), str(content_type or "image/png"))
        for image_bytes, content_type in images
        if image_bytes
    ]
    if not normalized_images:
        raise ValueError("DeepSeek视觉调用至少需要一张有效图片")

    api_key = resolve_deepseek_api_key(project_dir)
    if not api_key:
        raise RuntimeError(
            "缺少DeepSeek API密钥；请设置DEEPSEEK_FLASH_API_KEY/DEEPSEEK_API_KEY，"
            "或在项目.secrets目录放置deepseek_flash_api_key.txt/deepseek_api_key.txt"
        )

    from openai import OpenAI

    base_url = resolve_deepseek_base_url()
    model = resolve_deepseek_vision_model()
    detail = resolve_deepseek_vision_detail()
    max_tokens = resolve_deepseek_vision_max_tokens()
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
    image_count = len(normalized_images)
    labeled_prompt = (
        f"{prompt}\n\n本次共提供{image_count}个按阅读顺序排列的图片分块。"
        "必须逐块检查，不得跳过任何分块；相邻分块可能存在重叠，重复人物只输出一次。"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": labeled_prompt}]
    for image_index, (image_bytes, content_type) in enumerate(normalized_images, start=1):
        content.append(
            {
                "type": "text",
                "text": f"图片分块 {image_index}/{image_count}",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": build_image_data_url(image_bytes, content_type),
                    "detail": detail,
                },
            }
        )
    messages = [
        {
            "role": "system",
            "content": "你是严谨的中文图片信息抽取器。只能依据用户图片，必须输出合法JSON，禁止编造。",
        },
        {"role": "user", "content": content},
    ]
    request_options = {
        "model": model,
        "temperature": 0,
        "messages": messages,
        "max_tokens": max_tokens,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    started_at = time.perf_counter()
    try:
        response = client.chat.completions.create(
            **request_options,
            response_format={"type": "json_object"},
        )
    except Exception as error:
        error_text = str(error).lower()
        if "response_format" not in error_text and "json_object" not in error_text:
            raise
        response = client.chat.completions.create(**request_options)
    elapsed_seconds = time.perf_counter() - started_at
    raw_text = response.choices[0].message.content if response.choices else ""
    usage = response.usage
    return DeepSeekVisionResult(
        payload=parse_vision_json_object(str(raw_text or "")),
        raw_text=str(raw_text or ""),
        model=str(response.model or model),
        base_url=base_url,
        prompt_hash=sha256_text(labeled_prompt),
        input_hash=hash_images(normalized_images),
        elapsed_seconds=elapsed_seconds,
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
    )

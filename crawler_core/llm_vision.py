from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from crawler_core.fetcher import build_requests_headers
from crawler_core.models import PersonRecord


DEFAULT_VISION_MODEL = "gpt-4o-mini"
PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_API_KEY_FILE = PROJECT_DIR / ".secrets" / "openai_api_key.txt"
DEFAULT_DEEPSEEK_API_KEY_FILE = PROJECT_DIR / ".secrets" / "deepseek_api_key.txt"
DEFAULT_PROVIDER_FILE = PROJECT_DIR / ".secrets" / "llm_provider.txt"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"


def compact_text(value: object) -> str:
    """压缩空白，避免模型输出破坏 TXT 表格结构。"""
    return " ".join(str(value or "").split()).strip()


def get_llm_strategy(rule: dict[str, Any]) -> dict[str, Any]:
    """读取脚本中的大模型视觉策略。"""
    strategy = rule.get("llm_strategy")
    return strategy if isinstance(strategy, dict) else {}


def find_target_image_url(rule: dict[str, Any], html: str, final_url: str) -> str:
    """根据脚本标注的选择器定位目标图片 URL。"""
    strategy = get_llm_strategy(rule)
    selector = str(strategy.get("target_image_selector") or rule.get("leader_region_selector") or "").strip()
    base_url = final_url or str(rule.get("url", ""))
    soup = BeautifulSoup(html, "html.parser")
    if selector:
        node = soup.select_one(selector)
        if node is not None:
            src = str(node.get("src") or node.get("data-src") or node.get("data-original") or "").strip()
            if src:
                return urljoin(base_url, src)
    image_url_hint = str(strategy.get("image_url_hint") or "").strip()
    if image_url_hint:
        return urljoin(base_url, image_url_hint)
    raise ValueError(f"大模型视觉解析未定位到目标图片：{selector or '未配置选择器'}")


def download_image_bytes(image_url: str, page_url: str, timeout_seconds: int) -> tuple[bytes, str]:
    """下载待识别图片。"""
    headers = build_requests_headers(image_url, referer=page_url)
    headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    try:
        response = requests.get(image_url, timeout=timeout_seconds, verify=False, headers=headers)
    except requests.exceptions.SSLError:
        if not str(image_url).lower().startswith("https://"):
            raise
        fallback_url = "http://" + str(image_url)[len("https://") :]
        fallback_headers = build_requests_headers(fallback_url, referer=page_url)
        fallback_headers["Accept"] = headers["Accept"]
        response = requests.get(fallback_url, timeout=timeout_seconds, verify=False, headers=fallback_headers)
    response.raise_for_status()
    content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if not content_type or content_type == "application/octet-stream":
        suffix = image_url.rsplit("?", 1)[0].rsplit(".", 1)[-1].lower()
        content_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(suffix, "image/jpeg")
    if not content_type.startswith("image/"):
        raise ValueError(f"目标资源不是图片：{image_url}，Content-Type={content_type}")
    return response.content, content_type


def build_data_url(image_bytes: bytes, content_type: str) -> str:
    """构造 OpenAI 视觉接口可识别的 data URL。"""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def build_prompt(rule: dict[str, Any], image_url: str) -> str:
    """构造视觉抽取提示词。"""
    strategy = get_llm_strategy(rule)
    instruction = compact_text(strategy.get("instruction"))
    organization = compact_text(rule.get("organization"))
    page_url = compact_text(rule.get("url"))
    return (
        "请从图片中抽取领导人员信息，只返回 JSON，不要输出解释。\n"
        "JSON 格式必须为：{\"rows\":[{\"name\":\"姓名\",\"duty\":\"职务\",\"evidence\":\"图片中对应原文\"}]}。\n"
        "要求：只抽取图片中明确出现的姓名和现任职务；不要根据常识补全；姓名和职务均为空的行不要输出；"
        "如果图片中没有领导姓名职务，返回 {\"rows\":[]}。\n"
        f"机构：{organization}\n"
        f"页面：{page_url}\n"
        f"图片：{image_url}\n"
        f"补充要求：{instruction}"
    )


def read_api_key_from_file(path: Path) -> str:
    """从本地私密文件读取 API Key。"""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def resolve_llm_provider(rule: dict[str, Any]) -> str:
    """读取当前大模型供应商。"""
    strategy = get_llm_strategy(rule)
    provider = str(strategy.get("provider") or os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider:
        return provider
    if DEFAULT_PROVIDER_FILE.is_file():
        provider = DEFAULT_PROVIDER_FILE.read_text(encoding="utf-8", errors="ignore").strip().lower()
        if provider:
            return provider
    return "openai"


def resolve_openai_api_key() -> str:
    """按环境变量、本地私密文件的顺序读取 OpenAI API Key。"""
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key
    custom_key_file = os.environ.get("OPENAI_API_KEY_FILE", "").strip()
    if custom_key_file:
        key = read_api_key_from_file(Path(custom_key_file))
        if key:
            return key
    return read_api_key_from_file(DEFAULT_API_KEY_FILE)


def resolve_deepseek_api_key() -> str:
    """按环境变量、本地私密文件的顺序读取 DeepSeek API Key。"""
    env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        return env_key
    custom_key_file = os.environ.get("DEEPSEEK_API_KEY_FILE", "").strip()
    if custom_key_file:
        key = read_api_key_from_file(Path(custom_key_file))
        if key:
            return key
    return read_api_key_from_file(DEFAULT_DEEPSEEK_API_KEY_FILE)


def call_deepseek_text_json(prompt: str, source_text: str, timeout_seconds: int) -> dict[str, Any]:
    """调用 DeepSeek 文本模型，从 OCR 文本中抽取 JSON。"""
    api_key = resolve_deepseek_api_key()
    if not api_key:
        raise RuntimeError(f"缺少 DEEPSEEK_API_KEY，且未找到本地密钥文件：{DEFAULT_DEEPSEEK_API_KEY_FILE}")
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL") or DEEPSEEK_BASE_URL,
        timeout=timeout_seconds,
    )
    model = os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL).strip() or DEEPSEEK_DEFAULT_MODEL
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "你是严谨的信息抽取器。必须输出合法 JSON，不得编造来源文本中不存在的信息。",
            },
            {
                "role": "user",
                "content": f"{prompt}\n\nOCR文本：\n{source_text}",
            },
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    if not content:
        raise RuntimeError("DeepSeek 文本解析返回为空")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise RuntimeError(f"DeepSeek 文本解析未返回 JSON：{content[:200]}")
        return json.loads(match.group(0))


def call_openai_vision(image_data_url: str, prompt: str, timeout_seconds: int) -> dict[str, Any]:
    """调用 OpenAI 兼容视觉模型，返回 JSON 对象。"""
    api_key = resolve_openai_api_key()
    if not api_key:
        raise RuntimeError(f"缺少 OPENAI_API_KEY，且未找到本地密钥文件：{DEFAULT_API_KEY_FILE}")
    from openai import OpenAI

    model = os.environ.get("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL).strip() or DEFAULT_VISION_MODEL
    client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
        timeout=timeout_seconds,
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "你是严谨的信息抽取器。必须输出合法 JSON，且不得编造图片中不存在的信息。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    if not content:
        raise RuntimeError("大模型视觉解析返回为空")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise RuntimeError(f"大模型视觉解析未返回 JSON：{content[:200]}")
        return json.loads(match.group(0))


def normalize_model_rows(rule: dict[str, Any], payload: dict[str, Any], image_url: str) -> list[PersonRecord]:
    """将模型 JSON 结果规范为 PersonRecord。"""
    raw_rows = payload.get("rows") if isinstance(payload, dict) else []
    if not isinstance(raw_rows, list):
        raise RuntimeError("大模型视觉解析 JSON 缺少 rows 数组")
    rows: list[PersonRecord] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        name = compact_text(item.get("name"))
        duty = compact_text(item.get("duty"))
        evidence = compact_text(item.get("evidence")) or f"{name} {duty}".strip()
        if not name or not duty:
            continue
        rows.append(
            PersonRecord(
                organization=str(rule.get("organization", "")),
                url=str(rule.get("url", "")),
                name=name,
                duty=duty,
                detail_url="",
                evidence=f"图片识别：{evidence}；图片={image_url}",
                confidence=str(rule.get("confidence", "大模型视觉")),
                parser=str(rule.get("parser", "llm_vision_image_v1")),
                selector_summary=(
                    f"strategy=llm_vision；leader={rule.get('leader_region_selector', '')}；"
                    "name=大模型视觉识别姓名；duty=大模型视觉识别职务；detail=none"
                ),
            )
        )
    return rows


def parse_llm_vision_records(
    rule: dict[str, Any],
    html: str,
    final_url: str,
    snapshot_path: Path | None,
    timeout_seconds: int,
) -> list[PersonRecord]:
    """按脚本标注的图片选择器调用大模型视觉解析。"""
    image_url = find_target_image_url(rule, html, final_url)
    image_bytes, content_type = download_image_bytes(image_url, final_url or str(rule.get("url", "")), timeout_seconds)
    provider = resolve_llm_provider(rule)
    if provider == "deepseek":
        raise RuntimeError(
            "DeepSeek API 已配置，但当前官方 DeepSeek Chat 接口不支持图片输入；"
            "该图片页需要先配置本地 OCR，或改用支持视觉输入的模型/Codex 本机视觉"
        )
    if provider in {"codex_conversation", "codex_manual"}:
        raise RuntimeError("该图片页需在当前 Codex 对话中进行视觉识别，并将结果写回 TXT")
    if provider != "openai":
        raise RuntimeError(f"未知 llm_vision provider：{provider}")
    payload = call_openai_vision(build_data_url(image_bytes, content_type), build_prompt(rule, image_url), timeout_seconds)
    return normalize_model_rows(rule, payload, image_url)

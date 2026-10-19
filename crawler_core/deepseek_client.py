from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any


@dataclass(frozen=True)
class DeepSeekJsonResult:
    """记录一次可审计的DeepSeek JSON调用结果。"""

    payload: dict[str, Any]
    raw_text: str
    model: str
    base_url: str
    prompt_hash: str
    input_hash: str
    elapsed_seconds: float


def sha256_text(value: str) -> str:
    """计算UTF-8文本的SHA-256。"""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def read_secret(path: Path) -> str:
    """读取本地密钥文件，不向控制台或日志输出内容。"""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def read_environment_value(variable_name: str) -> str:
    """读取进程环境；Windows中新设置的变量尚未继承时再只读用户/系统环境。"""
    value = os.environ.get(variable_name, "").strip()
    if value or os.name != "nt":
        return value

    import winreg

    registry_locations = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for registry_root, registry_path in registry_locations:
        try:
            with winreg.OpenKey(registry_root, registry_path) as registry_key:
                registry_value, _ = winreg.QueryValueEx(registry_key, variable_name)
        except (FileNotFoundError, OSError):
            continue
        value = str(registry_value or "").strip()
        if value:
            return value
    return ""


def resolve_deepseek_api_key(project_dir: Path) -> str:
    """按环境变量、自定义文件、项目私密文件的顺序读取API密钥。"""
    for variable_name in ["DEEPSEEK_FLASH_API_KEY", "DEEPSEEK_API_KEY"]:
        value = read_environment_value(variable_name)
        if value:
            return value

    custom_path = read_environment_value("DEEPSEEK_API_KEY_FILE")
    if custom_path:
        value = read_secret(Path(custom_path))
        if value:
            return value

    for file_name in ["deepseek_flash_api_key.txt", "deepseek_api_key.txt"]:
        value = read_secret(project_dir / ".secrets" / file_name)
        if value:
            return value
    return ""


def resolve_deepseek_base_url() -> str:
    """读取DeepSeek Flash或标准DeepSeek兼容接口地址。"""
    return (
        read_environment_value("DEEPSEEK_FLASH_BASE_URL")
        or read_environment_value("DEEPSEEK_BASE_URL")
        or "https://api.deepseek.com"
    )


def resolve_deepseek_model() -> str:
    """读取实际模型ID；未配置时沿用项目现有文本模型默认值。"""
    return (
        read_environment_value("DEEPSEEK_FLASH_MODEL")
        or read_environment_value("DEEPSEEK_MODEL")
        or "deepseek-chat"
    )


def parse_json_object(raw_text: str) -> dict[str, Any]:
    """把模型响应解析为JSON对象，并兼容响应外围的少量文本。"""
    text = str(raw_text or "").strip()
    if not text:
        raise RuntimeError("DeepSeek返回为空")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise RuntimeError(f"DeepSeek未返回合法JSON：{text[:200]}")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise RuntimeError("DeepSeek JSON顶层必须是对象")
    return payload


def call_deepseek_json(
    prompt: str,
    source_label: str,
    source_text: str,
    project_dir: Path,
    timeout_seconds: int,
) -> DeepSeekJsonResult:
    """调用OpenAI兼容的DeepSeek Flash文本接口并返回严格JSON结果。"""
    api_key = resolve_deepseek_api_key(project_dir)
    if not api_key:
        raise RuntimeError(
            "缺少DeepSeek API密钥；请设置DEEPSEEK_FLASH_API_KEY/DEEPSEEK_API_KEY，"
            "或在项目.secrets目录放置deepseek_flash_api_key.txt/deepseek_api_key.txt"
        )

    from openai import OpenAI

    base_url = resolve_deepseek_base_url()
    model = resolve_deepseek_model()
    started_at = time.perf_counter()
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
    messages = [
        {
            "role": "system",
            "content": "你是严谨的信息抽取器。只能依据用户提供的原文，必须输出合法JSON，禁止编造。",
        },
        {
            "role": "user",
            "content": f"{prompt}\n\n{source_label}：\n{source_text}",
        },
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=messages,
        )
    except Exception as error:
        error_text = str(error).lower()
        if "response_format" not in error_text and "json_object" not in error_text:
            raise
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=messages,
        )
    raw_text = response.choices[0].message.content if response.choices else ""
    elapsed_seconds = time.perf_counter() - started_at
    return DeepSeekJsonResult(
        payload=parse_json_object(raw_text),
        raw_text=str(raw_text or ""),
        model=model,
        base_url=base_url,
        prompt_hash=sha256_text(prompt),
        input_hash=sha256_text(source_text),
        elapsed_seconds=elapsed_seconds,
    )

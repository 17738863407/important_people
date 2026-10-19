from __future__ import annotations

import re
from pathlib import Path

from crawler_core.rule_table import normalize_script_sequence


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def safe_filename_part(value: object, fallback: str = "未命名", max_length: int = 200) -> str:
    """把业务字段转换为稳定的 Windows 文件名片段。"""
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value or "").strip())
    text = re.sub(r"\s+", "_", text).strip(" ._")
    if not text:
        text = fallback
    if text.upper() in WINDOWS_RESERVED_NAMES:
        text = f"_{text}"
    return text[:max_length].rstrip(" .") or fallback


def build_artifact_stem(script_sequence: object, organization: object) -> str:
    """生成脚本与抽取结果共同使用的“脚本序号_机构名称”主体。"""
    sequence = normalize_script_sequence(script_sequence)
    if not re.fullmatch(r"\d{4}", sequence):
        raise ValueError(f"脚本序号必须是四位数字：{script_sequence}")
    organization_part = safe_filename_part(organization, fallback="未命名机构")
    return f"{sequence}_{organization_part}"


def build_script_name(script_sequence: object, organization: object) -> str:
    """生成规范 Python 脚本文件名。"""
    return f"{build_artifact_stem(script_sequence, organization)}.py"


def build_output_name(script_sequence: object, organization: object) -> str:
    """生成规范 TXT 抽取结果文件名。"""
    return f"{build_artifact_stem(script_sequence, organization)}.txt"


def script_sequence_from_filename(path_or_name: object) -> str:
    """从规范或历史文件名前缀读取四位脚本序号。"""
    name = Path(str(path_or_name or "")).name
    match = re.match(r"^(\d{4})_", name)
    return match.group(1) if match else ""

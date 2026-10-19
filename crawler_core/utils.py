from __future__ import annotations

from functools import lru_cache
import re
from pathlib import Path
from typing import Any


def compact_text(value: Any) -> str:
    """压缩文本空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


@lru_cache(maxsize=16)
def read_terms(v3_dir: Path, relative_path: str) -> tuple[str, ...]:
    """读取 V3 内部黑名单词表。"""
    path = v3_dir / relative_path
    if not path.is_file():
        return tuple()
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            terms.append(text)
    return tuple(terms)


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    """判断文本是否包含任一词。"""
    return any(term in text for term in terms)


def clean_name(name: Any, v3_dir: Path) -> str:
    """姓名清洗与黑名单过滤。"""
    text = compact_text(name)
    text = re.sub(r"^(?:姓名|领导姓名)\s*[:：]", "", text)
    text = re.sub(r"(?:同志|先生|女士|简历)$", "", text)
    text = re.sub(r"[\s　]+", "", text).strip("：:，,、；;()（）[]【】")
    if not re.fullmatch(r"[一-鿿·]{2,20}", text):
        return ""
    if len(text) > 12 and "·" not in text:
        return ""
    if contains_any(text, read_terms(v3_dir, "workspace/module/黑名单_姓名_包含词.txt")):
        return ""
    if text in read_terms(v3_dir, "workspace/module/黑名单_姓名_精确词.txt"):
        return ""
    return text


def clean_duty(duty: Any, v3_dir: Path) -> str:
    """职务清洗与明显噪声过滤。"""
    text = compact_text(duty)
    text = re.sub(r"^(?:现任职务|职务|职位|岗位)\s*[:：]", "", text)
    text = text.strip("：:，,、；;。")
    if not text:
        return ""
    if re.search(r"(?:版权所有|ICP备|公网安备|联系电话|电话|传真|邮箱|地址|邮编|责任编辑|信息来源|点击量)", text):
        return ""
    return text[:300]

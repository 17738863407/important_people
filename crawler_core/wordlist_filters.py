from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


WORDLIST_DIR = Path(__file__).resolve().parents[1] / "workspace" / "module"


@dataclass(frozen=True)
class Wordlists:
    """弱结构解析使用的五类筛选词表。"""

    name_contains: frozenset[str]
    name_exact: frozenset[str]
    duty_contains: frozenset[str]
    duty_exact: frozenset[str]
    weak_duty_hints: frozenset[str]


def _read_words(path: Path) -> frozenset[str]:
    if not path.exists():
        return frozenset()
    words: list[str] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            word = line.strip()
            if not word or word in seen:
                continue
            seen.add(word)
            words.append(word)
    return frozenset(words)


@lru_cache(maxsize=1)
def load_wordlists() -> Wordlists:
    """加载五类规范词表。强结构解析器不得调用本函数。"""
    return Wordlists(
        name_contains=_read_words(WORDLIST_DIR / "黑名单_姓名_包含词.txt"),
        name_exact=_read_words(WORDLIST_DIR / "黑名单_姓名_精确词.txt"),
        duty_contains=_read_words(WORDLIST_DIR / "黑名单_职务_包含词.txt"),
        duty_exact=_read_words(WORDLIST_DIR / "黑名单_职务_精确词.txt"),
        weak_duty_hints=_read_words(WORDLIST_DIR / "白名单_弱结构职务提示词.txt"),
    )


def is_bad_name_for_weak_structure(value: str) -> bool:
    """弱结构候选姓名排噪。强结构解析器禁止使用。"""
    text = str(value or "").strip()
    if not text:
        return True
    wordlists = load_wordlists()
    if text in wordlists.name_exact:
        return True
    return any(word in text for word in wordlists.name_contains)


def is_bad_duty_for_weak_structure(value: str) -> bool:
    """弱结构候选职务排噪。强结构解析器禁止使用。"""
    text = str(value or "").strip()
    if not text:
        return True
    wordlists = load_wordlists()
    if text in wordlists.duty_exact:
        return True
    return any(word in text for word in wordlists.duty_contains)


def has_weak_duty_hint(value: str) -> bool:
    """判断弱结构文本是否包含职务提示词。"""
    text = str(value or "").strip()
    if not text:
        return False
    wordlists = load_wordlists()
    return any(word in text for word in wordlists.weak_duty_hints)

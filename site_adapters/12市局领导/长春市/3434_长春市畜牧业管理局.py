from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3434",
    "page_type": "多人物详情合并页",
    "structure_group": "changchun_animal_husbandry_profile_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_animal_husbandry_current_sentence_v1",
    "leader_region_selector": "#zoom_1",
    "name_selector": "人物块开头姓名及性别标记",
    "duty_selector": "当前人物块内完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#zoom_1"],
        "exclude_selectors": ["iframe", "script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "现任、历任与分工同处正文；仅在当前人物块内提取完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_profile_block_current_sentence",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom_1",
            "name_selector": "profile_block_name_before_gender",
            "duty_selector": "current_sentence_within_same_profile_block",
            "detail_link_selector": "",
        },
        "api": {"enabled": False, "reason": "原始HTML正文直接包含全部人物简介和现任句"},
        "migration": {
            "source": "legacy_full_page_text_regex",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


PERSON_BLOCK_PATTERN = re.compile(
    r"(?P<name>[\u4e00-\u9fff]{2,4})[：:](?:男|女)[，,](?P<body>.+?)"
    r"(?=(?:[\u4e00-\u9fff]{2,4})[：:](?:男|女)[，,]|$)"
)
CURRENT_SENTENCE_PATTERN = re.compile(r"现任[：:]?[^。]*。")


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文人物顺序，在每个人物块内提取完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        return []
    text = clean_text(content.get_text(" ", strip=True))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block_match in PERSON_BLOCK_PATTERN.finditer(text):
        name = block_match.group("name")
        current_match = CURRENT_SENTENCE_PATTERN.search(block_match.group("body"))
        if current_match is None or name in seen:
            continue
        evidence = clean_text(current_match.group(0)).removeprefix("现任").lstrip("：:").strip().removesuffix("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=zoom_1；evidence=current_sentence_within_person_block",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

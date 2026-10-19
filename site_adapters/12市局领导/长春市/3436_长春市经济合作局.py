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
    "rule_id": "3436",
    "page_type": "多人物详情合并页",
    "structure_group": "changchun_economic_cooperation_current_clause_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_economic_cooperation_current_clause_v1",
    "leader_region_selector": "#zoom_1",
    "name_selector": "现任标记前姓名",
    "duty_selector": "当前人物现任标记至首个逗号",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "长春市经济合作局领导分工",
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
    "risk_flag": "现任职务后紧接分工；只保留现任标记至首个逗号的原文职务证据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_name_current_clause",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom_1",
            "name_selector": "han_name_before_current_marker",
            "duty_selector": "current_marker_to_first_comma",
            "detail_link_selector": "",
        },
        "api": {"enabled": False, "reason": "原始HTML正文直接包含全部领导现任职务与分工"},
        "migration": {
            "source": "legacy_full_page_text_regex_fixed_name_anchor",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


PERSON_CURRENT_PATTERN = re.compile(
    r"(?<![\u4e00-\u9fff])"
    r"(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})\s+"
    r"(?P<current>现任\s*[^,，。]+)[,，。]"
)


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def compact_chinese_spacing(text: str) -> str:
    cleaned = clean_text(text)
    return re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序提取各人物现任职务逗号前原文，不纳入后续分工。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        return []
    text = clean_text(content.get_text(" ", strip=True))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in PERSON_CURRENT_PATTERN.finditer(text):
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            compact_chinese_spacing(match.group("current")),
        )
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=zoom_1；evidence=current_clause_before_comma；work_division=excluded",
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

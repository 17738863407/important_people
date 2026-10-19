from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """规范化页面排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按国资委领导专栏卡片顺序提取姓名、职务与详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in soup.select("a.ld-item[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})\s+(.+)", text)
        if match is None:
            continue
        name, duty = match.group(1), clean_text(match.group(2))
        key = (name, duty)
        if not duty or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_sasac_ld_item_v2",
                "selector_summary": "leader=a.ld-item[href]；name=链接首段；duty=姓名后原文；detail=href",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0846",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_sasac_ld_item",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_sasac_ld_item_v2",
    "leader_region_selector": "a.ld-item[href]",
    "name_selector": "链接文本首段姓名",
    "duty_selector": "姓名后原始文本",
    "detail_link_selector": "a.ld-item[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["a.ld-item[href]"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a.ld-item[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "a.ld-item[href]",
            "name_selector": "链接文本首段姓名",
            "duty_selector": "姓名后原始文本",
            "detail_link_selector": "a.ld-item[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["a.ld-item[href]"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态领导专栏已提供完整强结构卡片"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

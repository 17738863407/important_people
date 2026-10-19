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


PAGE_RULE = {
    "rule_id": "0334",
    "page_type": "人物列表完整页",
    "structure_group": "changsha_finance_name_duty_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changsha_finance_name_duty_list_v1",
    "leader_region_selector": "div.xxgk-list li",
    "name_selector": "a[href]",
    "duty_selector": "span",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.xxgk-list"],
        "exclude_selectors": ["header", "footer", "script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_link_from_list_item",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "列表同时提供姓名、职务和详情链接；仅限xxgk-list领导区域",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_strong_name_duty_list",
    "locator": {
        "css": {
            "leader_region_selector": "div.xxgk-list li",
            "name_selector": "same_item_anchor_text",
            "duty_selector": "same_item_span_text",
            "detail_link_selector": "same_item_anchor_href",
        },
        "api": {"enabled": False, "reason": "原始HTML列表直接提供姓名、职务及详情链接"},
        "migration": {
            "source": "legacy_online_list_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,8}")


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表DOM顺序提取姓名、职务和同项详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        anchor = item.select_one("a[href]")
        duty_node = item.select_one("span")
        if anchor is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", clean_text(anchor.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if NAME_PATTERN.fullmatch(name) is None or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(anchor.get("href") or "").strip()),
                "source_text": duty,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=xxgk_leader_list；name=anchor；duty=span；detail=same_anchor_href",
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

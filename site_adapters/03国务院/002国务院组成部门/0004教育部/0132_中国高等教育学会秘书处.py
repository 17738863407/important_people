from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0132", "page_type": "人物列表完整页", "structure_group": "cahe_secretariat_exact_groups_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cahe_secretariat_exact_groups_v1",
    "leader_region_selector": ".page_leader_title", "name_selector": "group_parent a[href] p", "duty_selector": "exact_group_title", "detail_link_selector": "group_parent a[href]",
    "content_scope": {"start_anchor": "秘书长", "end_anchor": "理事会名单", "include_selectors": [".page_leader_section"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "static_http", "detail_link_selector": ".page_leader_title + * a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "页面同时含会长、副会长、监事长等分组；只抽取标题精确等于秘书长或副秘书长的父级人物链接", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_exact_secretariat_groups",
    "locator": {"css": {"leader_region_selector": ".page_leader_title", "group_titles": ["秘书长", "副秘书长"], "name_selector": "parent a[href] p"}, "api": {"enabled": False, "reason": "原始HTML分组标题与人物卡片直接提供姓名、职务和独立详情链接"}, "migration": {"source": "legacy_business_source_and_regex_html_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for title in soup.select(page_rule["leader_region_selector"]):
        duty = clean_text(title.get_text(" ", strip=True))
        if duty not in {"秘书长", "副秘书长"} or title.parent is None:
            continue
        for link in title.parent.select("a[href]"):
            name_node = link.select_one("p")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            key = (name, duty)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or key in seen:
                continue
            seen.add(key)
            href = link.get("href", "")
            detail_url = "" if href.startswith("javascript:") else urljoin(final_url, href)
            rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；groups=秘书长_and_副秘书长；name=parent_link_p；detail=card_href；order=group_then_dom"})
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

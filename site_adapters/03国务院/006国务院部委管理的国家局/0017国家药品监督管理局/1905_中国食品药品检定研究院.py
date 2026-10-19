from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1905", "page_type": "人物列表完整页", "structure_group": "nifdc_leader_list_name_ntitle_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_nifdc_leader_list_name_ntitle_v1",
    "leader_region_selector": ".yp-fxjc-r .leader-listnew", "name_selector": ".name", "duty_selector": ".ntitle中br后最后文本段", "detail_link_selector": "",
    "content_scope": {"start_anchor": "院领导", "end_anchor": "相关链接", "include_selectors": [".yp-fxjc-r"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "旧脚本硬编码人物名单和机构全称边界；当前每个leader-listnew以name和ntitle强字段直出，ntitle首段为展示机构、末段为职务", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_leader_cards_last_ntitle_segment",
    "locator": {"css": {"leader_region_selector": ".yp-fxjc-r .leader-listnew", "name_selector": ".name", "duty_selector": ".ntitle:last_text_segment"}, "api": {"enabled": False, "reason": "原始HTML领导卡片直接提供姓名、展示机构和职务"}, "migration": {"source": "legacy_fixed_people_business_source_and_entry_detail_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(page_rule["leader_region_selector"]):
        name_node = card.select_one(".name")
        title_node = card.select_one(".ntitle")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        segments = [clean_text(value) for value in title_node.stripped_strings] if title_node else []
        duty = segments[-1] if len(segments) >= 2 else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_listnew；fields=name_ntitle_last_segment；order=dom"})
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

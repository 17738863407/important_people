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
    "rule_id": "2119", "page_type": "单人物详情页", "structure_group": "zhengzhou_public_single_leader_name_em_v1", "reuse_scope": "same_site_structure", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "single_detail", "collector": "static_http", "parser": "page_inline_zhengzhou_public_single_leader_name_em_v1",
    "leader_region_selector": ".main-body .content-wrap[aria-label='领导介绍']", "name_selector": ".content-leader-name > span", "duty_selector": ".content-leader-name > em", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导介绍", "end_anchor": "", "include_selectors": [".main-body .content-wrap[aria-label='领导介绍']"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 1},
    "risk_flag": "规则入口当前为单人物介绍页而非列表页；详情链接不得重复填写与依据入口相同的URL", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_single_leader_direct_fields",
    "locator": {"css": {"leader_region_selector": ".main-body .content-wrap[aria-label='领导介绍']", "name_selector": ".content-leader-name > span", "duty_selector": ".content-leader-name > em"}, "api": {"enabled": False, "reason": "原始HTML直接提供当前人物姓名与职务字段"}, "migration": {"source": "legacy_list_profile_and_business_source_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []
    name_node = region.select_one(page_rule["name_selector"])
    duty_node = region.select_one(page_rule["duty_selector"])
    name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
    duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
    if not name or not duty:
        return []
    return [{"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=content_wrap_leader_intro；fields=leader_name_span_em；detail_url=entry_page_omitted"}]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

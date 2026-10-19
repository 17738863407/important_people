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
    "rule_id": "2082", "page_type": "人物列表完整页", "structure_group": "zhengzhou_public_leader_anchor_span_b_v1", "reuse_scope": "same_site_structure", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_zhengzhou_public_leader_anchor_span_b_v1",
    "leader_region_selector": ".common-box a[href]", "name_selector": ":scope > span", "duty_selector": ":scope > b", "detail_link_selector": ".common-box a[href]",
    "content_scope": {"start_anchor": "机构领导", "end_anchor": "", "include_selectors": [".common-box"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "direct_links", "detail_collector_type": "static_http", "detail_link_selector": ".common-box a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "旧脚本使用未注册解析器名称并保留业务源副本；现按机构领导容器内直属span、b强结构提取", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_leader_anchor_direct_fields",
    "locator": {"css": {"leader_region_selector": ".common-box a[href]", "name_selector": ":scope > span", "duty_selector": ":scope > b", "detail_link_selector": "same_anchor_href"}, "api": {"enabled": False, "reason": "原始HTML直接提供当前领导姓名、职务与独立详情链接"}, "migration": {"source": "legacy_business_source_and_unregistered_parser_name_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(page_rule["leader_region_selector"]):
        name_node = anchor.select_one(":scope > span")
        duty_node = anchor.select_one(":scope > b")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=common_box_leader_links；fields=direct_span_b；order=dom"})
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

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
    "rule_id": "0336", "page_type": "人物列表完整页", "structure_group": "cse_grouped_leader_lists_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cse_grouped_leader_lists_v2",
    "leader_region_selector": "div.lead_list", "name_selector": "div.lead_list_con li p", "duty_selector": "h5.lead_list_title", "detail_link_selector": "div.lead_list_con li a[href]",
    "content_scope": {"start_anchor": "会长", "end_anchor": "Copyright", "include_selectors": ["div.lead_list"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "static_http", "detail_link_selector": "div.lead_list_con li a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "同一人物可在不同职务分组重复出现；按网页分组及卡片顺序逐项保留，不跨组拼接职务", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_grouped_leader_lists",
    "locator": {"css": {"leader_region_selector": "div.lead_list", "name_selector": "div.lead_list_con li p", "duty_selector": "h5.lead_list_title", "detail_link_selector": "li a[href]"}, "api": {"enabled": False, "reason": "原始HTML领导分组直接提供职务、姓名和独立详情链接"}, "migration": {"source": "legacy_cross_group_merge_and_business_source_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for group in soup.select(page_rule["leader_region_selector"]):
        title = group.select_one("h5.lead_list_title")
        duty = clean_text(title.get_text(" ", strip=True) if title else "")
        if not duty:
            continue
        for item in group.select("div.lead_list_con li"):
            name_node, link = item.select_one("p"), item.select_one("a[href]")
            raw_name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            name = re.sub(r"[（(][^）)]*[）)]$", "", raw_name).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
                continue
            detail_url = urljoin(final_url, link.get("href", "")) if link else ""
            rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=lead_list；duty=group_title；name=li_p；detail=card_href；order=group_then_dom"})
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

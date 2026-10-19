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
    "rule_id": "3286", "page_type": "人物列表完整页", "structure_group": "ywcbs_management_cards_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_ywcbs_management_cards_v1",
    "leader_region_selector": ".list_about_sld_ul li", "name_selector": ".t1", "duty_selector": ".t2", "detail_link_selector": "a[_href]",
    "content_scope": {"start_anchor": "班子成员", "end_anchor": "Copyright", "include_selectors": [".list_about_sld_ul"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "static_http", "detail_link_selector": ".list_about_sld_ul li a[_href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "详情地址保存在自定义_href属性，必须由对应人物卡片动态解析", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_management_cards_custom_href",
    "locator": {"css": {"leader_region_selector": ".list_about_sld_ul li", "name_selector": ".t1", "duty_selector": ".t2", "detail_link_selector": "a[_href]"}, "api": {"enabled": False, "reason": "原始HTML班子卡片直接提供姓名、职务与详情地址"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(page_rule["leader_region_selector"]):
        n, d, link = card.select_one(".t1"), card.select_one(".t2"), card.select_one("a[_href]")
        name = clean_text(n.get_text(" ", strip=True) if n else "").replace(" ", "")
        duty = clean_text(d.get_text(" ", strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
            href = link.get("_href", "") if link else ""
            rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, href) if href else "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=list_about_sld；name=t1；duty=t2；detail=custom_href；order=dom"})
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

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
    "rule_id": "0255", "page_type": "多人物详情合并页", "structure_group": "cnaes_current_leader_cards_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cnaes_current_leader_cards_v1",
    "leader_region_selector": "div.xrld-list div.item", "name_selector": "div.name", "duty_selector": "div.title", "detail_link_selector": "",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "Copyright", "include_selectors": ["div.xrld-list"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "限定现任领导xrld-list，排除历任经历和新闻人物", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_current_leader_cards",
    "locator": {"css": {"leader_region_selector": "div.xrld-list div.item", "name_selector": "div.name", "duty_selector": "div.title"}, "api": {"enabled": False, "reason": "原始HTML现任领导卡片直接提供姓名与职务"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(page_rule["leader_region_selector"]):
        n, d = card.select_one("div.name"), card.select_one("div.title")
        name = clean_text(n.get_text(" ", strip=True) if n else "").replace(" ", "")
        duty = clean_text(d.get_text(" ", strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=xrld-list；name=name；duty=title；order=dom"})
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

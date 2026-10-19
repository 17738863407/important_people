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
    "rule_id": "1110", "page_type": "多人物详情合并页", "structure_group": "caas_home_leader_detail_v2", "reuse_scope": "single_page", "load_mode": "静态列表与动态详情", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http_plus_browser_detail", "parser": "page_inline_caas_home_leader_detail_v2",
    "leader_region_selector": ".sub_nav1_2 div.item", "name_selector": "a.title[href*='zzjg/yld/']", "duty_selector": "detail .title .tip", "detail_link_selector": "a.title[href*='zzjg/yld/']",
    "content_scope": {"start_anchor": "院领导", "end_anchor": "历任领导", "include_selectors": [".sub_nav1_2"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": True, "mode": "custom_list_to_detail", "detail_collector_type": "browser_dom", "detail_link_selector": "a.title[href*='zzjg/yld/']", "detail_parser": "detail_tip_v2", "detail_name_selector": ".title.fs30", "detail_duty_selector": ".title .tip", "detail_content_selector": ".info_box", "max_detail_links": 20},
    "risk_flag": "权威入口首页仅有姓名和详情链接，职务需逐个在线渲染详情页取得；列表顺序必须恢复", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_home_list_browser_detail",
    "locator": {"css": {"leader_region_selector": ".sub_nav1_2 div.item", "name_selector": "a.title[href*='zzjg/yld/']", "detail_duty_selector": ".title .tip"}, "api": {"enabled": False, "reason": "首页静态列表与详情渲染DOM可复现"}, "migration": {"source": "legacy_business_source_and_local_file_dependency_removed", "verified_status": "verified_current_home_and_detail_dom", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one(page_rule["name_selector"])
        if link is None:
            continue
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(final_url, href)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not href or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="extract", force_browser=True, timeout=60)
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
            duty_node = detail_soup.select_one(page_rule["detail_strategy"]["detail_duty_selector"])
            duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""
        except Exception:
            duty = ""
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_list_to_browser_detail；scope=detail_title_tip；order=home_list_dom"})
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

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4380",
    "page_type": "研究所领导详情页集合",
    "structure_group": "gig_leader_sidebar_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_gig_leader_sidebar_details_v1",
    "leader_region_selector": ".contentLeft ul.leftNavigation",
    "name_selector": ".content .h1_gzdhs .tit_gzdhs",
    "duty_selector": ".content .style_dp_gzdhs .trs_editor_view > p:first-of-type",
    "detail_link_selector": ".contentLeft ul.leftNavigation a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".contentLeft ul.leftNavigation", ".content"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "sidebar_detail_pages"},
    "risk_flag": "入口为首位领导详情页，需按侧栏顺序逐页读取姓名和首段职务",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验侧栏为现任领导列表且各链接指向独立详情页",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".contentLeft ul.leftNavigation", "name_selector": ".content .h1_gzdhs .tit_gzdhs", "duty_selector": ".content .style_dp_gzdhs .trs_editor_view > p:first-of-type", "detail_link_selector": ".contentLeft ul.leftNavigation a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".contentLeft ul.leftNavigation", ".content"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "侧栏和各领导详情内容均为静态HTML"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_detail(detail_html: str, detail_url: str, parser: str) -> dict[str, str] | None:
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".content .h1_gzdhs .tit_gzdhs")
    duty_nodes = soup.select(".content .style_dp_gzdhs .trs_editor_view > p")
    if name_node is None or not duty_nodes:
        return None
    name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
    duty = next((clean_text(node.get_text(" ", strip=True)) for node in duty_nodes if clean_text(node.get_text(" ", strip=True))), "")
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty:
        return None
    return {"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": parser, "selector_summary": "侧栏领导链接对应详情页标题+正文首段职务"}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(".contentLeft ul.leftNavigation a[href]")
    if not links:
        return []
    session = requests.Session()
    session.trust_env = False
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, link in enumerate(links):
        detail_url = urljoin(final_url, link.get("href", ""))
        detail_html = html
        if index > 0:
            response = session.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_html = response.text
        row = parse_detail(detail_html, detail_url, str(page_rule.get("parser", "")))
        if row is None or row["name"] in seen:
            continue
        seen.add(row["name"])
        rows.append(row)
    if len(rows) != len(links):
        raise RuntimeError(f"领导详情解析不完整：侧栏{len(links)}项，成功{len(rows)}项")
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

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
    "rule_id": "2819",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_veterans_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_veterans_directory_details_v1",
    "leader_region_selector": "ul.ldjj",
    "name_selector": "ul.ldjj li a；详情.ldname",
    "duty_selector": "详情.ldzw",
    "detail_link_selector": "ul.ldjj li a[href]",
    "content_scope": {"start_anchor": "机构信息", "end_anchor": "", "include_selectors": ["ul.ldjj"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "directory_details", "detail_collector_type": "static_http", "detail_link_selector": "ul.ldjj li a[href]", "detail_name_selector": ".ldname", "detail_duty_selector": ".ldzw", "detail_content_selector": ".ydldxq-name", "max_detail_links": 50},
    "risk_flag": "详情.trs_editor_view为工作分工而非职务；必须读取.ldname/.ldzw强字段，禁止快照依赖和机构前缀删减",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "ul.ldjj li", "name_selector": "a及详情.ldname", "duty_selector": ".ldzw", "detail_link_selector": "a[href]", "content_scope": {"start_anchor": "人物姓名", "end_anchor": "工作分工", "include_selectors": [".ydldxq-name"], "exclude_selectors": [".trs_editor_view"]}},
        "api": {"enabled": False, "reason": "当前静态HTML目录提供人物链接，详情页.ldname/.ldzw直接提供姓名和职务"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _parse_detail(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".ldname")
    duty_node = soup.select_one(".ldzw")
    return (_clean_name(name_node.get_text(" ", strip=True)) if name_node else "",
            _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序在线解析详情姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("ul.ldjj li"):
        link = item.find("a", href=True)
        expected_name = _clean_name(item.get_text(" ", strip=True))
        if not link or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", expected_name) or expected_name in seen:
            continue
        detail_html, detail_url = _fetch_detail(urljoin(base_url, str(link.get("href", ""))))
        name, duty = _parse_detail(detail_html)
        if name != expected_name or not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty,
                     "parser": "custom_tianjin_veterans_directory_details_v1",
                     "selector_summary": "ul.ldjj人物目录；详情.ldname/.ldzw强字段"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

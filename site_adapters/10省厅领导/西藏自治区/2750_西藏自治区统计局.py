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
    "rule_id": "2750",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_statistics_duty_name_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xizang_statistics_duty_name_links_v1",
    "leader_region_selector": "ul.ttln",
    "name_selector": "ul.ttln li a.ttln[href]文本末尾姓名",
    "duty_selector": "ul.ttln li a.ttln[href]文本姓名前职务",
    "detail_link_selector": "ul.ttln li a.ttln[href]",
    "content_scope": {
        "start_anchor": "领导之窗",
        "end_anchor": "",
        "include_selectors": ["ul.ttln li a.ttln[href]"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": "ul.ttln li a.ttln[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "姓名与职务位于同一链接文本，按末尾姓名边界解析；详情链接只取当前人物列表项href",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.ttln",
            "name_selector": "li a.ttln[href]文本末尾",
            "duty_selector": "li a.ttln[href]文本姓名之前",
            "detail_link_selector": "li a.ttln[href]",
            "content_scope": {
                "start_anchor": "首条领导链接",
                "end_anchor": "末条领导链接",
                "include_selectors": ["ul.ttln li a.ttln[href]"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML人物链接直接提供职务、姓名和独立详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物列表DOM顺序解析“职务 姓名”链接。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    pattern = re.compile(r"^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,6})$")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("ul.ttln li a.ttln[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href", ""))),
                "evidence": duty,
                "parser": "custom_xizang_statistics_duty_name_links_v1",
                "selector_summary": "ul.ttln a.ttln链接；文本职务+末尾姓名",
            }
        )
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

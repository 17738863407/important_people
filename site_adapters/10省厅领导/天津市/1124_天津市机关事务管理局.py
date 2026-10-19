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
    "rule_id": "1124",
    "page_type": "现任领导信息页",
    "structure_group": "tianjin_jgsw_leader_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_jgsw_leader_links_v1",
    "leader_region_selector": "div.xl-content",
    "name_selector": ".xl-r2-list a[title]标题首段",
    "duty_selector": ".xl-r2-list a[title]标题姓名后部分",
    "detail_link_selector": ".xl-r2-list a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["div.xl-content .xl-r2-list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "card_links",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.xl-content .xl-r2-list a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "源文件名曾标记浏览器DOM待确认；当前HTTP响应已完整直出领导列表，标题属性同时包含姓名和职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.xl-content .xl-r2-list",
            "name_selector": "a[title]标题首段",
            "duty_selector": "a[title]标题姓名后部分",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": ["div.xl-content .xl-r2-list"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前HTTP静态HTML已完整提供领导姓名、职务和独立详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表DOM顺序解析标题中的姓名、职务及独立链接。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("div.xl-content .xl-r2-list a[href]"):
        text = _clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)", text)
        if not match:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        detail_url = urljoin(base_url, str(link.get("href", "")))
        if not duty or name in seen or detail_url.rstrip("/") == base_url.rstrip("/"):
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_jgsw_leader_links_v1",
                "selector_summary": "div.xl-content .xl-r2-list a；title首段姓名及后续职务",
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

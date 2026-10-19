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
    "rule_id": "0589",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_fzgg_leader_detail_menu",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_fzgg_leader_detail_menu_v1",
    "leader_region_selector": ".leader-pic",
    "name_selector": ".leader-name",
    "duty_selector": ".leader-office",
    "detail_link_selector": ".two-menu a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "网站地图",
        "include_selectors": [".leader-pic"],
        "exclude_selectors": [".leader-block"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "current_page_menu",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".leader-pic .two-menu a[href]",
        "detail_name_selector": ".leader-pic .leader-name",
        "detail_duty_selector": ".leader-pic .leader-office",
        "detail_content_selector": ".leader-pic",
        "max_detail_links": 50,
    },
    "risk_flag": "规则入口兼作首位领导详情页；首人详情链接与入口同址须留空，联系电话和领导分工不得写入职务依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".leader-pic",
            "name_selector": ".leader-name",
            "duty_selector": ".leader-office",
            "detail_link_selector": ".two-menu a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "网站地图",
                "include_selectors": [".leader-pic"],
                "exclude_selectors": [".leader-block"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML侧栏提供人物目录，详情页强字段直接包含姓名和职务",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    """清理姓名中的网页排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_html(url: str) -> tuple[str, str]:
    """在线获取人物详情页HTML及最终地址。"""
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _parse_detail(html: str) -> tuple[str, str]:
    """从详情页强字段读取姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".leader-pic .leader-name")
    offices = [_clean_text(node.get_text(" ", strip=True)) for node in soup.select(".leader-pic .leader-office")]
    name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
    duty = next((value for value in offices if value and not value.startswith("联系电话")), "")
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口页人物目录顺序抓取详情，并恢复原始顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_url = str(page_rule.get("url", final_url))
    base_url = final_url or entry_url
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select(".leader-pic .two-menu a[href]"):
        expected_name = _clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(base_url, str(link.get("href", "")))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", expected_name)
            or "/ldxx_47326/" not in detail_url
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        candidates.append((expected_name, detail_url))

    rows: list[dict[str, str]] = []
    for expected_name, candidate_url in candidates:
        if candidate_url.rstrip("/") == base_url.rstrip("/"):
            detail_html, resolved_url = html, base_url
        else:
            detail_html, resolved_url = _fetch_html(candidate_url)
        name, duty = _parse_detail(detail_html)
        if name != expected_name or not duty:
            continue

        detail_url = "" if resolved_url.rstrip("/") == entry_url.rstrip("/") else resolved_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_fzgg_leader_detail_menu_v1",
                "selector_summary": ".two-menu人物目录；详情.leader-name/.leader-office强字段",
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

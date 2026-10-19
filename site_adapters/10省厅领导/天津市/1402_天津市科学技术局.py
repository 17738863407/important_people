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
    "rule_id": "1402",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_science_leader_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_science_leader_details_v1",
    "leader_region_selector": ".left_menu_ul",
    "name_selector": ".left_menu_ul a[title]",
    "duty_selector": ".people_parts .part2中现任标签后的首个非空p",
    "detail_link_selector": ".left_menu_ul a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".left_menu_ul", ".people_parts"],
        "exclude_selectors": ["footer", ".more_nav_ul"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "left_menu_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".left_menu_ul a[href]",
        "detail_name_selector": ".people_parts .part1 span",
        "detail_duty_selector": ".people_parts .part2中现任标签后的首个非空p",
        "detail_content_selector": ".people_parts",
        "max_detail_links": 50,
    },
    "risk_flag": "规则入口兼作首位领导详情页；详情职务位于独立现任标签后的下一非空段，禁止使用固定人物职务回退",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".left_menu_ul",
            "name_selector": ".left_menu_ul a[title]",
            "duty_selector": ".people_parts .part2中现任标签后的首个非空p",
            "detail_link_selector": ".left_menu_ul a[href]",
            "content_scope": {
                "start_anchor": "现任：",
                "end_anchor": "",
                "include_selectors": [".people_parts"],
                "exclude_selectors": ["footer", ".more_nav_ul"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML左侧目录及8个详情页直接提供姓名、现任标签和职务字段",
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


def _fetch_detail(url: str) -> tuple[str, str]:
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
    """从详情页现任标签后的强字段读取姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    parts = soup.select_one(".people_parts")
    if parts is None:
        return "", ""
    name_node = parts.select_one(".part1 span")
    name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in parts.select(".part2 p")]
    paragraphs = [value for value in paragraphs if value]
    for index, value in enumerate(paragraphs):
        if value.rstrip("：:") == "现任" and index + 1 < len(paragraphs):
            return name, paragraphs[index + 1].rstrip("。.")
        if value.startswith("现任"):
            duty = re.sub(r"^现任[:：]?", "", value).strip()
            if duty:
                return name, duty.rstrip("。.")
    return name, ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧领导目录顺序在线解析8个详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".left_menu_ul")
    if region is None:
        return []
    entry_url = str(page_rule.get("url", final_url))
    base_url = final_url or entry_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in region.select("a[href]"):
        expected_name = _clean_name(str(link.get("title") or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", expected_name) or expected_name in seen:
            continue
        candidate_url = urljoin(base_url, str(link.get("href", "")))
        if candidate_url.rstrip("/") == base_url.rstrip("/"):
            detail_html, resolved_url = html, base_url
        else:
            detail_html, resolved_url = _fetch_detail(candidate_url)
        name, duty = _parse_detail(detail_html)
        if name != expected_name or not duty:
            continue

        detail_url = "" if resolved_url.rstrip("/") == entry_url.rstrip("/") else resolved_url
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_science_leader_details_v1",
                "selector_summary": ".left_menu_ul目录；详情.people_parts姓名及现任标签后的职务p",
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

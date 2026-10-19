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
    "rule_id": "3431",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_government_service_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_government_service_leader_cards_v1",
    "leader_region_selector": "ul.people_list",
    "name_selector": "ul.people_list li .name",
    "duty_selector": "ul.people_list li .text_con",
    "detail_link_selector": "ul.people_list li > a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["ul.people_list li"],
        "exclude_selectors": [".img_con"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_js_redirect",
        "detail_collector_type": "static_http",
        "detail_link_selector": "ul.people_list li > a[href]",
        "detail_name_selector": ".name",
        "detail_duty_selector": ".text_con",
        "detail_content_selector": "人物最终页",
        "max_detail_links": 50,
    },
    "risk_flag": "人物卡片href先进入location.replace跳转页；须在线解析最终地址并校验页面含对应姓名，职务仅取卡片.text_con",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.people_list",
            "name_selector": "li .name",
            "duty_selector": "li .text_con",
            "detail_link_selector": "li > a[href]",
            "content_scope": {
                "start_anchor": "首个人物卡片",
                "end_anchor": "末个人物卡片",
                "include_selectors": ["ul.people_list li"],
                "exclude_selectors": [".img_con"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML人物卡片直接提供姓名与职务，详情由卡片链接的可复现脚本跳转获得",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def _fetch(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _resolve_detail_url(landing_url: str, expected_name: str) -> str:
    landing_html, landing_final_url = _fetch(landing_url)
    match = re.search(r"location\.replace\(\s*['\"]([^'\"]+)['\"]\s*\)", landing_html)
    candidate_url = urljoin(landing_final_url, match.group(1)) if match else landing_final_url
    detail_html, detail_final_url = _fetch(candidate_url)
    detail_text = _clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
    return detail_final_url if expected_name in detail_text else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片DOM顺序提取字段，并在线解析人物页脚本跳转。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("ul.people_list li"):
        name_node = item.select_one(".name")
        duty_node = item.select_one(".text_con")
        link = item.select_one("a[href]")
        if name_node is None or duty_node is None or link is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        detail_url = _resolve_detail_url(urljoin(base_url, str(link.get("href", ""))), name)
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_government_service_leader_cards_v1",
                "selector_summary": "ul.people_list人物卡片；.name姓名；.text_con职务；href脚本跳转最终页",
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

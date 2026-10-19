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

PAGE_RULE = {'rule_id': '0064',
 'domain': 'agri.hainan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hainan_agri_leader_cards_v1',
 'leader_region_selector': 'div.nytldy-l a[href]:has(em)',
 'name_selector': 'em',
 'duty_selector': 'p',
 'detail_link_selector': 'div.nytldy-l a[href]:has(em)',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
             'locator': {'css': {'leader_region_selector': 'div.nytldy-l a[href]:has(em)',
                     'name_selector': 'em',
                     'duty_selector': 'p',
                                 'detail_link_selector': 'div.nytldy-l a[href]:has(em)',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def script_duty(card: BeautifulSoup) -> str:
    """从领导卡片内生成职务文字的脚本变量读取原值。"""
    for script in card.find_all("script"):
        match = re.search(r"var\s+zw\s*=\s*['\"](?P<duty>[^'\"]+)['\"]", str(script.string or ""))
        if match:
            return clean_text(match.group("duty"))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    cards = soup.select("div.nytldy-l a[href]:has(em)")
    if not cards:
        response = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div.nytldy-l a[href]:has(em)")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div.nytldy-l a[href]:has(em)；"
        "name=em；duty=p内var zw；detail=div.nytldy-l a[href]:has(em)；api_enabled=False"
    )
    for card in cards:
        name_node = card.select_one("em")
        duty_node = card.select_one("p")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "") or script_duty(card)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(source_url, card.get("href", "")),
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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

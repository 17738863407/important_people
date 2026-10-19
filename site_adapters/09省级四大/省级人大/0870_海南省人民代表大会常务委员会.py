from __future__ import annotations

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

PAGE_RULE = {'rule_id': '0870',
 'domain': 'www.hainanpc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hainan_pc_director_sections_v1',
 'leader_region_selector': '.director-section',
 'name_selector': '.director-list-item_name',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'risk_flag': '原规则缺少核心选择器，通用解析输出空行；需按主任会议成员分组解析',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.director-section',
                     'name_selector': '.director-list-item_name',
                     'duty_selector': '',
                     'detail_link_selector': 'a.director-list-item',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩人大常委会主任会议成员卡片文本空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析海南省人大常委会主任会议成员分组列表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = str(page_rule.get("url", "")) or final_url
    selector_summary = "strategy=custom_parse_page；section=.director-section；duty=.director-title-text；name=.director-list-item_name"

    try:
        response = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.RequestException:
        if not soup.select_one(".director-section"):
            return rows

    for section in soup.select(".director-section"):
        duty_node = section.select_one(".director-title-text")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        for item in section.select("a.director-list-item"):
            name_node = item.select_one(".director-list-item_name")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            if not name or not duty or name in seen:
                continue
            seen.add(name)
            detail_url = urljoin(source_url, str(item.get("href", "")))
            if detail_url.rstrip("/") == source_url.rstrip("/"):
                detail_url = ""
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", "")) or source_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
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

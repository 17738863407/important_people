from __future__ import annotations

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

PAGE_RULE = {'rule_id': '1631',
 'domain': 'mof.hainan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'hainan_mof_leader_cards_v1',
 'leader_region_selector': 'html > body > div.ww:nth-of-type(4) > div.nw:nth-of-type(1) > div.erji > '
                           'div.gkpd.clear:nth-of-type(2) > div.gkpd-l:nth-of-type(1) > div.gkpd-l-nr > '
                           'div.gkpd-ldd:nth-of-type(3)',
 'name_selector': '',
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
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.ww:nth-of-type(4) > div.nw:nth-of-type(1) > div.erji '
                                               '> div.gkpd.clear:nth-of-type(2) > div.gkpd-l:nth-of-type(1) > '
                                               'div.gkpd-l-nr > div.gkpd-ldd:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析海南省财政厅领导信息卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    if not soup.select(".gkpd-ld a[href], .gkpd-ldd a[href]"):
        import requests

        response = requests.get(page_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".gkpd-ld a[href], .gkpd-ldd a[href]"):
        name_node = link.select_one("em")
        duty_node = link.select_one("span")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        duty = duty.strip("[] \t\r\n")
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(page_url, str(link.get("href") or ""))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "hainan_mof_leader_cards_v1",
                "selector_summary": "leader=.gkpd-ld/.gkpd-ldd a; name=em; duty=span",
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

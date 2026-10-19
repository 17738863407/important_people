from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1791',
 'domain': 'mzt.shaanxi.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'shaanxi_mzt_leader_group_list_v1',
 'leader_region_selector': '.header-infos, .leader-list .item',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.main-box:nth-of-type(1) > div.container.white-box > '
                                               'div.am-g > div.left-card.am-u-lg-6:nth-of-type(1) > '
                                               'div.infos:nth-of-type(4) > div.leader-list:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析陕西省民政厅领导信息分组名单。"""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()

    def add_record(name: str, duty: str, href: str, selector_summary: str) -> None:
        name = _clean_text(name)
        duty = _clean_text(duty)
        if not name or not duty or name in seen_names:
            return
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            return
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(final_url, href) if href else "",
                "evidence": duty,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": selector_summary,
                "order": str(len(records) + 1),
            }
        )

    top = soup.select_one(".header-infos")
    if top:
        spans = top.select("span")
        link = top.select_one("a[href]")
        if len(spans) >= 2:
            add_record(
                spans[0].get_text(" ", strip=True),
                spans[1].get_text(" ", strip=True),
                link.get("href", "") if link else "",
                "section=.header-infos; name=span[0]; duty=span[1]",
            )

    for item in soup.select(".leader-list .item"):
        link = item.select_one(".name a[href]")
        duty_node = item.select_one("span")
        if link and duty_node:
            add_record(
                link.get_text(" ", strip=True),
                duty_node.get_text(" ", strip=True),
                link.get("href", ""),
                "section=.leader-list; item=.item; name=.name a; duty=span",
            )

    return records


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

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0790',
 'domain': 'gxt.nmg.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_online_nmg_gxt_ldjj_table_v1',
 'leader_region_selector': '#table1 tr',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '#table1 td a[href]',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '#table1 tr',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导简介页面表格直接给出姓名和职务'},
             'migration': {'source': 'online_static_table',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析领导简介页面表格。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []

    for tr in soup.select("#table1 tr"):
        cells = [cell for cell in tr.find_all("td") if cell.get_text(" ", strip=True)]
        if len(cells) < 2:
            continue
        name_cell = cells[1] if len(cells) >= 3 and cells[0].get_text(" ", strip=True).isdigit() else cells[0]
        duty_cell = cells[2] if len(cells) >= 3 and cells[0].get_text(" ", strip=True).isdigit() else cells[1]
        link = name_cell.find("a", href=True)
        name = re.sub(r"[\s\u3000\xa0]+", "", name_cell.get_text(" ", strip=True))
        duty = re.sub(r"[\s\u3000\xa0]+", "", duty_cell.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url or page_url, str(link.get("href", ""))) if link else "",
                "evidence": duty,
                "parser": parser,
                "selector_summary": "#table1 tr td姓名链接 + td职务",
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

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2506',
 'domain': 'smzt.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_guangdong_civil_affairs_leader_details_v1',
 'leader_region_selector': 'a[href*="/jggk/ldzc/"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href*="/jggk/ldzc/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href*="/jggk/ldzc/"]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '机构概况首页缺职务，在线逐页读取领导之窗详情',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'a[href*="/jggk/ldzc/"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': True}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析广东省民政厅领导之窗入口及详情页。"""
    source_url = str(page_rule["url"])
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one('a[href*="/jggk/ldzc/"]'):
        soup = BeautifulSoup(_fetch_html(source_url), "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/jggk/ldzc/"]'):
        name = _clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        if not 2 <= len(name) <= 4 or name == "领导之窗" or name in seen:
            continue
        detail_soup = BeautifulSoup(_fetch_html(detail_url), "html.parser")
        duty_node = detail_soup.select_one("#wdfg")
        duty = _clean_text(duty_node.get_text(" ", strip=True)).strip("。；; ") if duty_node else ""
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_guangdong_civil_affairs_leader_details_v1",
                "selector_summary": "机构概况领导链接 + 在线详情页#wdfg职务职级",
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

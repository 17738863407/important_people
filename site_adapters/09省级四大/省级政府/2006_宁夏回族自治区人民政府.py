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

PAGE_RULE = {'rule_id': '2006',
 'domain': 'www.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ningxia_government_leader_homepage_v1',
 'leader_region_selector': '.main-cell.leader-cell',
 'name_selector': '.header-top .leader-midBox .tit a:first-child, .vice-list a.cell .text',
 'duty_selector': '.second-box .tit, .header-top .leader-midBox .tit a.ml15',
 'detail_link_selector': '.header-top .leader-midBox .tit a[href], .vice-list a.cell[href]',
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
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.main-cell.leader-cell',
                     'name_selector': '.header-top .leader-midBox .tit a:first-child, .vice-list a.cell .text',
                     'duty_selector': '.second-box .tit, .header-top .leader-midBox .tit a.ml15',
                     'detail_link_selector': '.header-top .leader-midBox .tit a[href], .vice-list a.cell[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析宁夏回族自治区人民政府首页政府领导区域。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".main-cell.leader-cell")
    if region is None:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    def append_row(name: str, duty: str, href: str) -> None:
        name = _clean_text(name)
        duty = _clean_text(duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            return
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(base_url, href), "evidence": duty})

    title_links = region.select(".header-top .leader-midBox .tit a[href]")
    if len(title_links) >= 2:
        append_row(title_links[0].get_text(" ", strip=True), title_links[1].get_text(" ", strip=True), title_links[0].get("href", ""))
    for heading in region.select(".second-box"):
        duty_node = heading.select_one(".tit")
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        people_region = heading.find_next_sibling("div")
        if people_region is None or "vice-list" not in people_region.get("class", []):
            continue
        for link in people_region.select("a.cell[href]"):
            name_node = link.select_one(".text")
            append_row(name_node.get_text(" ", strip=True) if name_node else "", duty, link.get("href", ""))
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

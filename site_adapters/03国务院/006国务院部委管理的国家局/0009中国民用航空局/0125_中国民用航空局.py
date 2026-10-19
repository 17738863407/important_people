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

PAGE_RULE = {'rule_id': '0125',
 'domain': 'www.caac.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_home_caac_leader_box_v1',
 'leader_region_selector': 'div containing h2=局领导',
 'name_selector': 'first ul label a, second ul li span:last-child',
 'duty_selector': 'first ul following li span, second ul li span:first-child',
 'detail_link_selector': 'first ul label a[href]',
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
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div containing h2=局领导',
                     'name_selector': 'first ul label a, second ul li span:last-child',
                     'duty_selector': 'first ul following li span, second ul li span:first-child',
                     'detail_link_selector': 'first ul label a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '首页局领导模块静态 HTML 直接给出姓名和职务'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def find_leader_box(soup: BeautifulSoup):
    heading = soup.find("h2", string=lambda value: value and clean_text(value) == "局领导")
    if not heading:
        return None
    box = heading
    for _ in range(5):
        box = box.parent
        if box and len(box.select("ul")) >= 2:
            return box
    return heading.parent


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    box = find_leader_box(soup)
    if not box:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div containing h2=局领导；"
        "name=first ul label a, second ul li span:last-child；"
        "duty=first ul following li span, second ul li span:first-child；"
        "detail=first ul label a[href]；api_enabled=False"
    )
    first_ul, *other_uls = box.select("ul")
    items = first_ul.select("li")
    index = 0
    while index < len(items):
        link = items[index].select_one("label a[href]")
        if not link:
            index += 1
            continue
        name = clean_name(link.get_text(" ", strip=True))
        duty = ""
        if index + 1 < len(items):
            duty_node = items[index + 1].select_one("span")
            duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if name and duty and name not in seen:
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(base_url, link.get("href", "")),
                    "evidence": duty,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": selector_summary,
                }
            )
        index += 2

    for ul in other_uls:
        for item in ul.select("li"):
            spans = item.select("span")
            if len(spans) < 2:
                continue
            duty = clean_text(spans[0].get_text(" ", strip=True))
            name = clean_name(spans[-1].get_text(" ", strip=True))
            if not name or not duty or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
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

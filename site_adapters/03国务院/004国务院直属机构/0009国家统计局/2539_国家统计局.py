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

PAGE_RULE = {'rule_id': '2539',
 'domain': 'www.stats.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_nbs_leader_group_text_v1',
 'leader_region_selector': '局领导正文',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrapper > div.wrapper-content:nth-of-type(3) > '
                                               'div.wrapper-list > div.wrapper-list-right:nth-of-type(2) > '
                                               'div.jg-jld-content:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态页面正文已列出局领导及职务分组'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    region = soup.select_one(".jg-jld-content")
    if region is None:
        return rows
    head_link = region.select_one(".jg-jld-name a[href]")
    head_duty_node = region.select_one(".jg-jld-zw")
    if head_link and head_duty_node:
        name = _clean_text(head_link.get_text(" ", strip=True)).replace(" ", "")
        duty = _clean_text(head_duty_node.get_text(" ", strip=True))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, head_link.get("href", "")),
                "evidence": duty,
                "parser": "custom_nbs_leader_group_text_v1",
                "selector_summary": "局领导正文；姓名后职务及职务分组",
            }
        )
    grouped: dict[str, dict[str, object]] = {}
    for item in region.select(".jg-jld-zz-item"):
        title_node = item.select_one(".jg-jld-zz-name")
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
        for link in item.select(".jf-jld-zz-ry a[href]"):
            name = _clean_text(link.get_text(" ", strip=True)).replace(" ", "")
            if not name or not title:
                continue
            entry = grouped.setdefault(name, {"titles": [], "detail_url": urljoin(final_url, link.get("href", ""))})
            if title not in entry["titles"]:
                entry["titles"].append(title)
    for name, entry in grouped.items():
        duty = "；".join(entry["titles"])
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": entry["detail_url"],
                "evidence": duty,
                "parser": "custom_nbs_leader_group_text_v1",
                "selector_summary": "局领导正文；姓名后职务及职务分组",
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

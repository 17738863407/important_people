from __future__ import annotations

import html as html_lib
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

PAGE_RULE = {'rule_id': '2030',
 'domain': 'nync.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'liaoning_agriculture_department_leaders_v1',
 'leader_region_selector': '部门领导',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
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


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", text)
    return text.strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析机关简介页“部门领导”区块。"""
    soup = BeautifulSoup(html, "html.parser")
    title = next(
        (node for node in soup.select(".xxgk_tt") if _clean_text(node.get_text(" ", strip=True)) == "部门领导"),
        None,
    )
    region = title.find_next_sibling("ul") if title else None
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"^(?P<duty>.+(?:书记|厅长|主任|组长|监察官|局长|总队长)(?:（[^）]{1,20}）)?)(?P<name>[\u4e00-\u9fa5·]{2,4})$"
    )
    for link in region.select("dd a[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        records.append({
            "name": name,
            "duty": duty,
            "detail_url": urljoin(final_url, str(link.get("href", ""))),
            "evidence": duty,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "title=.xxgk_tt 部门领导；region=next ul.provincial-leaders-inner；fields=dd a text",
        })
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

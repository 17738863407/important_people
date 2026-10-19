from __future__ import annotations

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2673',
 'domain': 'szrd.fjrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_fujian_people_congress_group_text_v1',
 'leader_region_selector': '主任会议成员分组文本',
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
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _add_rows(rows: list[dict], page_rule: dict, names_text: str, duty: str) -> None:
    for name in re.findall(r"[\u4e00-\u9fff]{2,4}", names_text):
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_fujian_people_congress_group_text_v1",
                "selector_summary": "主任会议成员分组文本",
            }
        )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"人大机构 主\s*任 (?P<chair>.+?) 副主任 (?P<vice>.+?) 秘书长 (?P<secretary>[\u4e00-\u9fff]{2,4})", text)
    if not match:
        return []
    rows: list[dict] = []
    _add_rows(rows, page_rule, match.group("chair"), "主任")
    _add_rows(rows, page_rule, match.group("vice"), "副主任")
    _add_rows(rows, page_rule, match.group("secretary"), "秘书长")
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

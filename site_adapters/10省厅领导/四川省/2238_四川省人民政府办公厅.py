from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2238',
 'domain': 'www.sc.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'sichuan_gov_office_leader_intro_v1',
 'leader_region_selector': 'div.newp.leader',
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
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.newp.leader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导简介块直接列出办公厅领导姓名和分工职务'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'fixed',
                           'behavior_changed': True}}}


def _make_record(page_rule: dict, name: str, duty: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url="",
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析四川省人民政府办公厅领导简介块，避开机构设置正文噪声。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str]] = []
    for paragraph in soup.select("div.newp.leader p"):
        text = paragraph.get_text(" ", strip=True)
        boundary = re.search(r"省(?:政府|纪委)", text)
        if not boundary:
            continue
        name = re.sub(r"\s+", "", text[: boundary.start()])
        duty = re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", re.sub(r"\s+", " ", text[boundary.start() :])).strip(" ，、；")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) and duty:
            rows.append((name, duty))
    return [_make_record(page_rule, name, duty) for name, duty in rows]


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

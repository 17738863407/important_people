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

PAGE_RULE = {'rule_id': '2232',
 'domain': 'www.sasac.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'sasac_leader_piclist_v1',
 'leader_region_selector': 'table.picList',
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
 'locator': {'css': {'leader_region_selector': 'div#l-normalcon1 > div.sublist:nth-of-type(1) > table.picList',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '委领导图片列表直接包含姓名、职务和详情链接'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _make_record(page_rule: dict, name: str, duty: str, href: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=href,
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析国务院国资委委领导图片列表。"""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for item in soup.select("table.picList dl"):
        name_node = item.select_one("dd p")
        link = item.select_one("a[href]")
        script = item.select_one("dd p script")
        name = "".join(name_node.stripped_strings).strip() if name_node else ""
        script_text = script.get_text(" ", strip=True) if script else ""
        duty_match = re.search(r'var\s+str\s*=\s*"([^"]+)"', script_text)
        duty = duty_match.group(1).replace("国务院国有资产监督管理委员会", "国资委") if duty_match else ""
        if not name or not duty or not link:
            continue
        records.append(_make_record(page_rule, name, duty, urljoin(final_url, link.get("href", ""))))
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

from __future__ import annotations

import sys
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2290',
 'domain': 'www.sdrd.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'shandong_people_congress_home_table_v1',
 'leader_region_selector': '包含“山东省第十四届人民代表大会常务委员会”的最小table',
 'name_selector': '领导表格内a[href]',
 'duty_selector': '领导表格内主任/副主任/秘书长标题',
 'detail_link_selector': '领导表格内a[href]',
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
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '首页领导表格与新闻公告混排，需限定常委会表格解析'},
             'migration': {'source': 'sequential_static_html_builder',
             'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def _clean_name(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = re.sub(r"[（(][男女][）)]", "", unescape(text))
    return re.sub(r"\s+", "", text).replace("\u3000", "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析山东省人大常委会首页领导表格。"""
    soup = BeautifulSoup(html, "html.parser")
    heading = "山东省第十四届人民代表大会常务委员会"
    candidates = [table for table in soup.select("table") if heading in table.get_text(" ", strip=True)]
    if not candidates:
        return []
    leader_table = min(candidates, key=lambda table: len(table.get_text(" ", strip=True)))
    base_url = final_url or str(page_rule.get("url", ""))
    records = []
    seen = set()
    current_duty = ""
    for node in leader_table.descendants:
        if isinstance(node, NavigableString) and (not node.parent or node.parent.name != "a"):
            token = _clean_name(str(node))
            duty_match = re.fullmatch(r"(主任|副主任|秘书长)[：:]", token)
            if duty_match:
                current_duty = duty_match.group(1)
            elif token.startswith("委员"):
                break
            continue
        if not isinstance(node, Tag) or node.name != "a" or not current_duty:
            continue
        name = _clean_name(node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        href = str(node.get("href", ""))
        detail_url = urljoin(base_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        seen.add(name)
        records.append(_make_record(page_rule, name, current_duty, detail_url))
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

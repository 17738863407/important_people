from __future__ import annotations

import html as html_lib
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

PAGE_RULE = {'rule_id': '2183',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'raw_http',
 'parser': 'ningxia_defense_mobilization_tab_profile_v2',
 'leader_region_selector': '.ldzc-content.ldzctab .ldzc-item .ldzc-wrap2 .view',
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
                     'max_detail_links': 0},
 'risk_flag': '增强请求会跟随页面脚本误跳转到站内搜索，需保留当前入口原始 HTML；注释内有旧职务，必须仅解析可见简介块',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldzc-content.ldzctab .ldzc-item .ldzc-wrap2 .view',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前入口原始 HTML 已包含全部可见人物简介'},
             'migration': {'source': 'current_online_raw_html',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s*([，、；：])\s*", r"\1", text)


def _make_record(page_rule: dict, name: str, duty: str, evidence: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url="",
        evidence=evidence,
        confidence="high",
        parser=page_rule["parser"],
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析领导之窗 tab 简介中的现任职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    if not soup.select(".ldzc-content.ldzctab .ldzc-item"):
        result = fetch_by_raw_requests(str(page_rule.get("url", final_url)))
        soup = BeautifulSoup(result.html, "html.parser")
    records: list[object] = []
    seen: set[str] = set()
    for item in soup.select(".ldzc-content.ldzctab .ldzc-item"):
        profile = item.select_one(".ldzc-wrap2 .view")
        if profile is None:
            continue
        text = _clean_text(profile.get_text(" ", strip=True))
        name_match = re.match(r"([\u4e00-\u9fff·]{2,5})[，,]", text)
        duty_match = re.search(r"现任(.*?)(?:。|$)", text)
        if not name_match or not duty_match:
            continue
        name = name_match.group(1)
        duty = _clean_text(duty_match.group(1)).rstrip("。；; ")
        if name in seen or not duty:
            continue
        seen.add(name)
        records.append(_make_record(page_rule, name, duty, duty))
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

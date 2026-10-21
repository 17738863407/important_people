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

PAGE_RULE = {'rule_id': '0613',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'lanzhou_police_zoom_responsibility_v1',
 'leader_region_selector': '#zoom p',
 'name_selector': '#zoom p（同志：前）',
 'duty_selector': '#zoom p（同志：后分工说明）',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '陈贵生同志',
                   'end_anchor': '为保证高效履行职责',
                   'include_selectors': ['#zoom'],
                   'exclude_selectors': []},
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
 'risk_flag': '页面为领导分工合并正文；原2026-01-15地址失效，已改为栏目当前2026-07-15在线地址；排除AB岗制度说明段',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#zoom p',
                     'name_selector': '#zoom p（同志：前）',
                     'duty_selector': '#zoom p（同志：后分工说明）',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '陈贵生同志',
                                       'end_anchor': '为保证高效履行职责',
                                       'include_selectors': ['#zoom'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线入口页正文已包含领导分工，无需请求详情页或接口'},
             'migration': {'source': 'sequential_manual_fix',
                           'verified_status': 'pending_root',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=#zoom p；name=姓名同志：前；"
        "duty=姓名同志：后分工说明；detail=none；api_enabled=False"
    )
    current_name = ""
    current_parts: list[str] = []

    def flush_current() -> None:
        nonlocal current_name, current_parts
        if not current_name or current_name in seen:
            current_name = ""
            current_parts = []
            return
        duty = clean_text(" ".join(current_parts))
        if not duty:
            current_name = ""
            current_parts = []
            return
        evidence = clean_text(f"{current_name}同志：{duty}")
        seen.add(current_name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": current_name,
                "duty": duty,
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
        current_name = ""
        current_parts = []

    for paragraph in soup.select("#zoom p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "为保证高效履行职责" in text:
            flush_current()
            break
        match = re.match(r"^(?P<name>[\u4e00-\u9fa5·]{2,5})同志[:：](?P<duty>.+)$", text)
        if match:
            flush_current()
            current_name = clean_text(match.group("name"))
            first_duty = clean_text(match.group("duty"))
            current_parts = [first_duty] if first_duty else []
            continue
        if current_name and text:
            current_parts.append(text)
    flush_current()
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

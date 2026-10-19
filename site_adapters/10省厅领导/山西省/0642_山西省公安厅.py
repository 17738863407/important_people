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

PAGE_RULE = {'rule_id': '0642',
 'domain': 'gatgw.shanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'shanxi_police_inline_paragraph_leaders_v1',
 'leader_region_selector': '.xl_zw .trs_editor_view p',
 'name_selector': '.xl_zw .trs_editor_view p 行首姓名',
 'duty_selector': '.xl_zw .trs_editor_view p 姓名后文本',
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
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.xl_zw .trs_editor_view p',
                     'name_selector': '.xl_zw .trs_editor_view p 行首姓名',
                     'duty_selector': '.xl_zw .trs_editor_view p 姓名后文本',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def compact_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ").replace("\u2002", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([，、。；;])", r"\1", text)
    text = re.sub(r"([，、；;])\s+", r"\1", text)
    return text


def split_name_duty(line: str) -> tuple[str, str]:
    text = compact_text(line)
    match = re.match(r"^(?P<name>[\u4e00-\u9fa5](?:\s*[\u4e00-\u9fa5]){1,3})\s+(?P<duty>.+)$", text)
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    duty = compact_text(match.group("duty")).strip(" ，,。；;")
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
        return "", ""
    if not any(token in duty for token in ("厅", "副省长", "纪检监察组", "公安局")):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.xl_zw .trs_editor_view p；"
        "name=段首姓名；duty=姓名后文本；detail=none；api_enabled=False"
    )
    for paragraph in soup.select(".xl_zw .trs_editor_view p"):
        source_text = compact_text(paragraph.get_text(" ", strip=True))
        name, duty = split_name_duty(source_text)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
        })
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

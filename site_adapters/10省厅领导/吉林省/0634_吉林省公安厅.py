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

PAGE_RULE = {'rule_id': '0634',
 'domain': 'gat.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'jilin_police_zoom_leader_info_v1',
 'leader_region_selector': '#zoom p',
 'name_selector': '#zoom p（二、厅长信息后段首姓名）',
 'duty_selector': '#zoom p（姓名后职务）',
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
                     'max_detail_links': 50},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#zoom p',
                     'name_selector': '#zoom p（二、厅长信息后段首姓名）',
                     'duty_selector': '#zoom p（姓名后职务）',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['#zoom'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线正文已包含领导信息静态段落，无需接口或详情页'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    in_leader_section = False
    selector_summary = (
        "strategy=custom_parse_page；leader=#zoom p；"
        "name=二、厅长信息后段首姓名；duty=姓名后职务；detail=none；api_enabled=False"
    )
    for paragraph in soup.select("#zoom p"):
        raw_text = paragraph.get_text(" ", strip=True)
        normalized = re.sub(r"[\u00a0\u3000]+", " ", raw_text or "")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        compact = clean_text(normalized)
        if "二、厅长信息" in compact:
            in_leader_section = True
            continue
        if not in_leader_section:
            continue
        if compact.startswith("负责人"):
            break
        match = re.match(r"^(?P<name>[\u4e00-\u9fa5](?:\s*[\u4e00-\u9fa5]){1,2})\s+(?P<duty>.+)$", normalized)
        if not match:
            continue
        name = clean_text(match.group("name"))
        duty = clean_text(match.group("duty")).strip(" ：:，,。")
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
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

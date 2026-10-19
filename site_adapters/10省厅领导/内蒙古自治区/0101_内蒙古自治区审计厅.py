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

PAGE_RULE = {'rule_id': '0101',
 'domain': 'audit.nmg.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_card_nmg_audit_leader_intro_v1',
 'leader_region_selector': 'div.g_ldjjnr div.ldjs_lb1',
 'name_selector': 'div.ldjs_lb1_mz',
 'duty_selector': 'div.ldjs_lb1_rightnr p:first non-heading',
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
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.g_ldjjnr div.ldjs_lb1',
                     'name_selector': 'div.ldjs_lb1_mz',
                     'duty_selector': 'div.ldjs_lb1_rightnr p:first non-heading',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导表格/卡片在静态 HTML 中直接给出姓名、职务、分工和简介'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div.g_ldjjnr div.ldjs_lb1；"
        "name=div.ldjs_lb1_mz；duty=div.ldjs_lb1_rightnr p:first non-heading；"
        "detail=none；api_enabled=False"
    )
    for card in soup.select("div.g_ldjjnr div.ldjs_lb1"):
        name = clean_name(card.select_one("div.ldjs_lb1_mz").get_text(" ", strip=True) if card.select_one("div.ldjs_lb1_mz") else "")
        paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in card.select("div.ldjs_lb1_rightnr p")]
        paragraphs = [p for p in paragraphs if p]
        duty = next((p for p in paragraphs if p not in {"分工", "简介"} and not p.startswith(f"{name}，")), "")
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

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

PAGE_RULE = {'rule_id': '2225',
 'domain': 'rst.shanxi.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'shanxi_hrss_leader_table_text_v1',
 'leader_region_selector': '#docContent .trs_editor_view',
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
 'locator': {'css': {'leader_region_selector': 'div#docContent > div.mainLeft_svxxgk > div.trs_editor_view.TRS_UEDITOR '
                                               '> div.trs_import_87d6rd.ue_table > table.trs_word_table',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '正文表格直接包含姓名、职务和工作分工'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'fixed',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩表格中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐行解析厅领导正文表格，不依赖固定姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for table_row in soup.select("#docContent .trs_editor_view table tr"):
        cells = table_row.find_all("td", recursive=False)
        if not cells:
            continue
        content_cell = cells[-1]
        first_paragraph = content_cell.find("p")
        if first_paragraph is None:
            continue
        bold_parts = [clean_text(node.get_text(" ", strip=True)) for node in first_paragraph.select("span[style*='font-weight:bold']")]
        bold_parts = [part for part in bold_parts if part]
        if len(bold_parts) < 2:
            continue
        name = re.sub(r"\s+", "", bold_parts[0])
        duty = clean_text("".join(bold_parts[1:])).strip(" ：:，,。；;")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "leader=#docContent .trs_editor_view table tr；field=last td first p bold spans",
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

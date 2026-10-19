from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2455',
 'domain': 'sjt.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V009_text_profile_paragraph_v1',
 'leader_region_selector': '',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\u2003", " ").replace("\xa0", " ").split())


def _extract_duty_from_detail(name: str, detail_url: str) -> str:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    detail_html = response.text
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    for node in detail_soup.select(".TRS_Editor p, .TRS_Editor"):
        text = _clean_text(node.get_text(" ", strip=True))
        if text.startswith(name):
            duty = _clean_text(text[len(name):])
            for marker in (" 工作分工", "工作分工", " 主持", "主持省"):
                if marker in duty:
                    duty = _clean_text(duty.split(marker, 1)[0])
                    break
            if duty:
                return duty
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析辽宁省审计厅部门领导列表，并从在线详情页补齐职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("dd.ldname a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not name or len(name) > 4 or name in seen:
            continue
        href = link.get("href", "").strip()
        detail_url = urljoin(final_url, href) if href else ""
        duty = _extract_duty_from_detail(name, detail_url)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
            "duty": re.sub(r"[（(]挂职[）)]", "", duty).strip(" ，,；;"),
                "detail_url": detail_url,
            "evidence": re.sub(r"[（(]挂职[）)]", "", duty).strip(" ，,；;"),
                "parser": "custom_liaoning_audit_detail_online_v1",
                "selector_summary": "dd.ldname a；详情.TRS_Editor首段",
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

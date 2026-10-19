from __future__ import annotations

import re
import sys
from html import unescape
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

PAGE_RULE = {'rule_id': '2327',
 'domain': 'sft.hebei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_hebei_sft_list_with_verified_duties_v1',
 'leader_region_selector': '.right_list li a',
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
 'risk_flag': '仅采用当前在线详情页职务',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.right_list li a',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页仅姓名，详情页核验职务后页面级映射输出'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析河北省司法厅厅领导列表，并使用已核验详情页职务。"""
    page_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    list_soup = BeautifulSoup(html, "html.parser")
    links = list_soup.select(".right_list li a[href]")
    if not links:
        response = requests.get(page_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        list_soup = BeautifulSoup(response.text, "html.parser")
        links = list_soup.select(".right_list li a[href]")
    for link in links:
        name = _clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(page_url, str(link.get("href") or ""))
        if not name or name in seen:
            continue
        response = requests.get(detail_url, timeout=30)
        if response.status_code != 200:
            continue
        response.encoding = response.apparent_encoding or "utf-8"
        scope = BeautifulSoup(response.text, "html.parser").select_one(".main_ct")
        detail_text = _clean_text(scope.get_text(" ", strip=True) if scope else "")
        duty = detail_text[len(name):].strip(" ，。；") if detail_text.startswith(name) else ""
        duty = re.sub(r"\s*【责任编辑[^】]*】.*$", "", duty).strip()
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).strip(" ，,、；;")
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty,
                     "parser": str(page_rule.get("parser", ""))})
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

from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3297',
 'domain': 'zfcxjst.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_online_detail_guizhou_housing_leader_v2',
 'leader_region_selector': '#Left_Nav li a[title]',
 'name_selector': '#Left_Nav li a[title]',
 'duty_selector': '详情页 .profile_right h2',
 'detail_link_selector': '#Left_Nav li a[title]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#Left_Nav li a[title]',
                     'name_selector': '#Left_Nav li a[title]',
                     'duty_selector': '详情页 .profile_right h2',
                     'detail_link_selector': '#Left_Nav li a[title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析贵州省住房和城乡建设厅领导之窗。"""
    from bs4 import BeautifulSoup

    def clean_text(value: str) -> str:
        return re.sub(r"[\s\u00a0\u3000]+", "", value or "")

    def fetch_detail_html(detail_url: str) -> str:
        response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        return response.text

    def extract_profile(profile_html: str) -> tuple[str, str]:
        soup = BeautifulSoup(profile_html, "html.parser")
        name_node = soup.select_one(".profile_right h3")
        duty_node = soup.select_one(".profile_right h2")
        name = clean_text(name_node.get_text("", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text("", strip=True) if duty_node else "")
        return name, duty

    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    current_name, current_duty = extract_profile(html)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("#Left_Nav li a[title]"):
        name = clean_text(link.get("title", "") or link.get_text("", strip=True))
        detail_url = urljoin(source_url, link.get("href", "").strip())
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        if name == current_name:
            duty = current_duty
        else:
            try:
                detail_name, duty = extract_profile(fetch_detail_html(detail_url))
            except Exception:
                continue
            if detail_name and detail_name != name:
                continue
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "#Left_Nav 姓名链接 + 在线详情页 h2 职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()

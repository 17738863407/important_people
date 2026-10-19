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

PAGE_RULE = {'rule_id': '3401',
 'domain': 'zrzy.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_liaoning_natural_resources_leader_v1',
 'leader_region_selector': '部门领导 a[href*="/bmld/"]',
 'name_selector': '部门领导链接文本',
 'duty_selector': '详情标题区职务',
 'detail_link_selector': 'a[href*="/bmld/"]',
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
 'locator': {'css': {'leader_region_selector': '部门领导 a[href*="/bmld/"]',
                     'name_selector': '部门领导链接文本',
                     'duty_selector': '详情标题区职务',
                     'detail_link_selector': 'a[href*="/bmld/"]',
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


def _load_detail_online(detail_url: str) -> str:
    try:
        response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return response.text
    except requests.RequestException:
        return ""


def _parse_detail_duty(detail_html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    text = re.sub(r"[\s\u00a0\u3000]+", " ", soup.get_text(" ", strip=True))
    duty_node = soup.select_one(".xxgk_ldlzw")
    duty = duty_node.get_text(" ", strip=True) if duty_node else ""
    current_match = re.search(r"现任辽宁省自然资源厅(.+?)。", text)
    if not duty and current_match:
        duty = current_match.group(1)
    duty = re.sub(r"\s+", "", duty).rstrip("，,；;。")
    evidence = (
        re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", current_match.group(0))
        if current_match
        else duty
    )
    return duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析辽宁省自然资源厅部门领导列表和在线详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/bmld/"]'):
        name = re.sub(r"[\s\u00a0\u3000]+", "", link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        duty, evidence = _parse_detail_duty(_load_detail_online(detail_url))
        if not duty or re.search(r"(负责|分管|工作|简介)", duty):
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": "部门领导链接+详情标题职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()

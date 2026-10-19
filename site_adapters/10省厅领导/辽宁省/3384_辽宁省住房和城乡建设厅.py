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

PAGE_RULE = {'rule_id': '3384',
 'domain': 'zjt.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_liaoning_housing_department_leader_v1',
 'leader_region_selector': '.ldname a[href]',
 'name_selector': '.ldname a 文本开头姓名',
 'duty_selector': '在线详情页简介现任句',
 'detail_link_selector': '.ldname a[href]',
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
 'locator': {'css': {'leader_region_selector': '.ldname a[href]',
                     'name_selector': '.ldname a 文本开头姓名',
                     'duty_selector': '在线详情页简介现任句',
                     'detail_link_selector': '.ldname a[href]',
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析辽宁省住房和城乡建设厅部门领导列表和在线详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ldname a[href]"):
        raw_text = re.sub(r"[\s\u00a0\u3000]+", " ", link.get_text(" ", strip=True)).strip()
        name_match = re.match(r"^([\u4e00-\u9fa5]{2,4})\s+(?:辽宁|纪检)", raw_text)
        if not name_match:
            continue
        name = name_match.group(1)
        if name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        detail_html = _load_detail_online(detail_url)
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detail_text = re.sub(r"\s+", "", detail_soup.get_text(" ", strip=True))
        duty_match = re.search(r"现任(.+?)(?:。|$)", detail_text)
        if not duty_match:
            continue
        duty = duty_match.group(1).rstrip("，,；;").replace("（挂职）", "").replace("(挂职)", "")
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".ldname名单+详情简介现任句",
            }
        )
    return rows


if __name__ == "__main__":
    main()

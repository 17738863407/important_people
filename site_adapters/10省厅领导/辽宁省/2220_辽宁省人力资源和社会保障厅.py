from __future__ import annotations

import html as html_lib
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

PAGE_RULE = {'rule_id': '2220',
 'domain': 'rst.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'liaoning_hrss_visible_leaders_v1',
 'leader_region_selector': '.provincial-leaders-inner',
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
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '部门领导可见区域给出姓名链接，职务由详情页现任句确认后映射'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", text)
    return text.strip()


def _fetch_current_duty(detail_url: str) -> tuple[str, str]:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one(".TRS_Editor") or soup
    text = re.sub(r"\s+", " ", region.get_text(" ", strip=True)).strip()
    match = re.search(r"现任[^。]*(?:。|$)", text)
    if match:
        duty = re.sub(r"[（(]挂职[）)]", "", match.group(0).removeprefix("现任").rstrip("。")).strip(" ，,；;")
        return duty, duty
    duty_node = soup.select_one(".xxgk_ldlzw")
    duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip() if duty_node else ""
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析辽宁省人社厅部门领导可见名单，排除注释中的旧数据。"""
    visible_html = re.sub(r"(?s)<!--.*?-->", "", html)
    section_match = re.search(r'(?is)<ul class="provincial-leaders-inner[^"]*"[^>]*>(.*?)</ul>', visible_html)
    source = section_match.group(1) if section_match else visible_html
    records: list[object] = []
    seen: set[str] = set()
    for href, inner_html in re.findall(r'(?is)<dd[^>]*>\s*<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</dd>', source):
        name = _clean_text(inner_html)
        detail_url = urljoin(final_url, href)
        try:
            duty, evidence = _fetch_current_duty(detail_url)
        except Exception:
            duty, evidence = "", ""
        if name and duty and name not in seen:
            seen.add(name)
            records.append({
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "visible ul.provincial-leaders-inner dd a；detail=现任句",
            })
    return records


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

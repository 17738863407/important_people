from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2550',
 'domain': 'sthj.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_liaoning_ecology_detail_online_v1',
 'leader_region_selector': '部门领导列表及详情页',
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
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '部门领导列表链接进入静态详情页解析'},
             'migration': {'source': 'online_static_detail_pages',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_duty(name: str, detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(rf"{re.escape(name)}\s*[：:].*?现任(?:现任)?(?:辽宁省生态环境厅)?\s*(?P<duty>.*?)(?:。|\s+工作分工)", text)
    return _clean_text(match.group("duty")).replace(" ", "") if match else ""


def _clean_evidence(value: str) -> str:
    """仅清理页面现任句的固定前后缀及尾随分工说明。"""
    value = re.sub(r"^现任(?:现任)?", "", value or "")
    value = re.split(r"\s*工作分工\s*[：:]", value, maxsplit=1)[0]
    return value.rstrip("。 ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    for link in soup.find_all("a"):
        name = _clean_text(link.get_text(" ", strip=True))
        href = link.get("href") or ""
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or "/bmld/" not in href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_html = response.text
        except requests.RequestException:
            continue
        if "找不到该页面" in detail_html:
            continue
        duty = _extract_duty(name, detail_html)
        if not duty:
            continue
        detail_text = _clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", detail_text)
        evidence = _clean_evidence(current_match.group(0) if current_match else f"现任{duty}。")
        seen.add(name)
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_liaoning_ecology_detail_online_v1",
                "selector_summary": "当前部门领导列表；详情页现任职务句",
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

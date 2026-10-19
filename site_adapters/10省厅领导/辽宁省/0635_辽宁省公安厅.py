from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0635',
 'domain': 'gat.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'liaoning_police_leader_detail_pages_v1',
 'leader_region_selector': 'a[href*="/bmld/"]',
 'name_selector': 'a[href*="/bmld/"]',
 'duty_selector': '详情页 .TRS_Editor 文本中“现任”后内容',
 'detail_link_selector': 'a[href*="/bmld/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'custom_parse_page_fetch_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href*="/bmld/"]',
                     'detail_parser': 'liaoning_police_detail_present_duty_v1',
                     'detail_name_selector': '目录页链接文本',
                     'detail_duty_selector': '详情页 .TRS_Editor 文本中“现任”后内容',
                     'detail_content_selector': '.TRS_Editor',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'medium',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
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
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """规范化网页正文空白，保留中文标点。"""
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def extract_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/bmld/"]'):
        name = clean_text(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href") or "")
        if not name or href in seen:
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen:
            continue
        seen.add(detail_url)
        links.append((name, detail_url))
    return links


def parse_detail_page(html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    content = soup.select_one(".TRS_Editor") or soup
    content_text = clean_text(content.get_text(" ", strip=True))
    duty = ""
    evidence = ""
    duty_match = re.search(r"现任(?P<duty>.+?)[。；;]", content_text)
    if duty_match:
        duty = clean_text(duty_match.group("duty")).strip(" ，,。；;")
        evidence = duty
    return clean_text(fallback_name), duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_online_html_with_fallback

    base_url = final_url
    links = extract_leader_links(html, base_url)
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=a[href*=bmld]；"
        "name=目录页部门领导链接文本；duty=详情页.TRS_Editor现任后；"
        "detail=a[href*=bmld]；api_enabled=False"
    )
    for fallback_name, detail_url in links:
        try:
            detail_html = fetch_online_html_with_fallback(detail_url, timeout=20).html
        except Exception:
            detail_html = ""
        name, duty, evidence = parse_detail_page(detail_html, fallback_name)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": evidence,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
        })
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

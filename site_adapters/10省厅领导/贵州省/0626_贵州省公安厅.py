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

PAGE_RULE = {'rule_id': '0626',
 'domain': 'gat.guizhou.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'guizhou_police_leader_detail_pages_v1',
 'leader_region_selector': '.ldzc',
 'name_selector': '.ldzc a[href*="/ldjj/"]；详情页.title p:first-child',
 'duty_selector': '.ldzc_left .title p:nth-child(2)；或.content现任后',
 'detail_link_selector': '.ldzc a[href*="/ldjj/"]',
 'content_scope': {'start_anchor': '领导简介',
                   'end_anchor': '',
                   'include_selectors': ['.ldzc'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_parse_page_fetch_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.ldzc a[href*="/ldjj/"]',
                     'detail_parser': 'guizhou_police_leader_detail_pages_v1',
                     'detail_name_selector': '.ldzc_left .title p:first-child',
                     'detail_duty_selector': '.ldzc_left .title p:nth-child(2)',
                     'detail_content_selector': '.ldzc_left',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldzc',
                     'name_selector': '.ldzc a[href*="/ldjj/"]；详情页.title p:first-child',
                     'duty_selector': '.ldzc_left .title p:nth-child(2)；或.content现任后',
                     'detail_link_selector': '.ldzc a[href*="/ldjj/"]',
                     'content_scope': {'start_anchor': '领导简介',
                                       'end_anchor': '',
                                       'include_selectors': ['.ldzc'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导信息为静态详情页 HTML，不是 JSON 接口'},
             'migration': {'source': 'sequential_manual_fix',
                           'verified_status': 'pending_root',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(".ldzc a[href]"):
        href = str(anchor.get("href") or "")
        if "/ldjj/" not in href:
            continue
        name = clean_text(anchor.get_text(" ", strip=True))
        detail_url = urljoin(base_url, href)
        if name and detail_url not in seen:
            links.append((name, detail_url))
            seen.add(detail_url)
    return links


def parse_detail(html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title_parts = [clean_text(p.get_text(" ", strip=True)) for p in soup.select(".ldzc_left .title p")]
    title_parts = [p for p in title_parts if p]
    name = clean_text(fallback_name)
    duty = title_parts[1] if len(title_parts) > 1 else (title_parts[0] if title_parts else "")
    area = soup.select_one(".ldzc_left .content") or soup.select_one(".content.clearfix") or soup
    area_text = clean_text(area.get_text(" ", strip=True))
    duty_match = re.search(r"现任(?P<duty>[^。]+?)。", area_text)
    if duty_match:
        duty = clean_text(duty_match.group("duty")).strip(" ，,。")
    duty = clean_text(duty).strip(" ：:，,。")
    duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).strip()
    return clean_text(name), duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_online_html_with_fallback

    source_url = str(page_rule.get("url", "")) or final_url
    links = extract_links(html, source_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = source_url.rstrip("/")
    selector_summary = (
        "strategy=custom_parse_page；leader=.ldzc；name=.ldzc a/详情.title首段；"
        "duty=详情.title第二段或现任后；detail=.ldzc a[href*=ldjj]；api_enabled=False"
    )
    for fallback_name, detail_url in links:
        detail_html = html if detail_url.rstrip("/") == source_url else ""
        if not detail_html:
            try:
                detail_html = fetch_online_html_with_fallback(detail_url, timeout=20).html
            except Exception:
                detail_html = ""
        name, duty, evidence = parse_detail(detail_html, fallback_name)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
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

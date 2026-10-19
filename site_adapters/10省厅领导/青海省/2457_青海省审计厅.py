from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2457',
 'domain': 'sjt.qinghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_qinghai_audit_jggk_online_v1',
 'leader_region_selector': '.ldjianjie',
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
 'risk_flag': '首页含新闻人物干扰；使用机构概况页和在线详情页',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.ldjianjie',
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
                           'behavior_changed': True}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    return "".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _fetch_online_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_duty_from_detail(name: str, detail_url: str) -> tuple[str, str]:
    detail_html = _fetch_online_html(detail_url)
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    content = detail_soup.select_one(".TRS_UEDITOR")
    text = _clean_text(content.get_text(" ", strip=True)) if content else ""
    compact_text = _clean_name(text)
    match = re.search(rf"{re.escape(name)}[:：]\s*(?P<duty>青海省审计厅[^。；]+)", compact_text)
    if match:
        return _clean_text(match.group("duty")), _clean_text(match.group("duty"))
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析青海省审计厅机构概况领导简介和在线详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    top_link = soup.select_one(".ldjjCon_ld h1 a[href]")
    if top_link:
        text = _clean_text(top_link.get_text(" ", strip=True))
        match = re.match(r"(?P<name>[一-鿿]{2,4})[:：]\s*青海省审计厅(?P<duty>.+)$", text)
        if match:
            name = _clean_name(match.group("name"))
            seen.add(name)
            rows.append(
                {
                    "organization": organization,
                    "url": source_url,
                    "name": name,
                    "duty": _clean_text(match.group("duty")),
                    "detail_url": urljoin(source_url, top_link.get("href", "").strip()),
                    "evidence": _clean_text(f"青海省审计厅{match.group('duty')}"),
                    "parser": "custom_qinghai_audit_jggk_online_v1",
                    "selector_summary": ".ldjjCon_ld h1 a；姓名：职务",
                }
            )

    for link in soup.select(".ldjjCon_name a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        detail_url = urljoin(source_url, link.get("href", "").strip())
        duty, evidence = _extract_duty_from_detail(name, detail_url)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_qinghai_audit_jggk_online_v1",
                "selector_summary": ".ldjjCon_name a；详情.TRS_UEDITOR",
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

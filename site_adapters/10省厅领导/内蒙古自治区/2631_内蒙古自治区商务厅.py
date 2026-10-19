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

PAGE_RULE = {'rule_id': '2631',
 'domain': 'swt.nmg.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'chrome_cdp',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_neimenggu_commerce_detail_online_v1',
 'leader_region_selector': '.LingDxl厅领导导航及在线详情页',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.LingDxl .left li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
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
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': '.LingDxl',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.LingDxl .left li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _extract_detail_duty(detail_html: str, name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    duty_node = soup.select_one(".LDxx1 p")
    if duty_node:
        return _clean_text(duty_node.get_text(" ", strip=True))
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(rf"厅领导\s+{re.escape(name)}\s+(?P<duty>.+?)\s+分工", text)
    if match:
        return _clean_text(match.group("duty"))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    legacy_links = soup.select(".LingDxl .left li a[href]")
    for link in legacy_links:
        name = _normalize_name(link.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(final_url or source_url, link.get("href") or "")
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_html = response.text
        except requests.RequestException:
            continue
        duty = _extract_detail_duty(detail_html, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_neimenggu_commerce_detail_online_v1",
                "selector_summary": ".LingDxl导航+在线详情页职务",
            }
        )

    if not legacy_links:
        for link in soup.select(".ldzc_box_left li a[href]"):
            name_node = link.select_one("span")
            duty_node = link.select_one("p")
            name = _normalize_name(name_node.get_text(" ", strip=True) if name_node else "")
            duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
            if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
                continue
            seen.add(name)
            rows.append(
                {
                    "organization": page_rule["organization"],
                    "url": page_rule["url"],
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(final_url or source_url, link.get("href") or ""),
                    "evidence": duty,
                    "parser": "custom_neimenggu_commerce_detail_online_v1",
                    "selector_summary": ".ldzc_box_left li a[href]；span姓名+p职务",
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

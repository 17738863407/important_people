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

PAGE_RULE = {'rule_id': '2630',
 'domain': 'swt.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'parser': 'custom_liaoning_commerce_detail_online_v1',
 'leader_region_selector': '部门领导姓名链接及在线详情页',
 'name_selector': '',
 'duty_selector': '',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href*="/bmld/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'online_static_detail_pages',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _extract_detail_duty(detail_html: str, name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    description = soup.select_one('meta[name="Description"][content]')
    content = _clean_text(str(description.get("content") or "")) if description else ""
    org_index = content.rfind("辽宁省商务厅")
    if org_index < 0:
        return ""
    duty = _clean_text(content[org_index + len("辽宁省商务厅"):]).removesuffix("。").strip()
    return duty if any(keyword in duty for keyword in ("书记", "厅长", "组长", "成员")) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    source_url = str(page_rule.get("url", final_url))
    current_url = source_url.replace("/zfxxgk/", "/zwgk/")
    rows: list[dict] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    response = session.get(current_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
    links = soup.select('a[href*="/bmld/"]')
    for link in links:
        name = _normalize_name(link.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(current_url, link.get("href") or "")
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            detail_html = response.content.decode("utf-8")
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
                "parser": "custom_liaoning_commerce_detail_online_v1",
                "selector_summary": "部门领导链接+在线详情页职务",
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

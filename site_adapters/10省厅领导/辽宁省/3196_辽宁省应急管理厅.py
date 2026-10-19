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

PAGE_RULE = {'rule_id': '3196',
 'domain': 'yjgl.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_liaoning_emergency_leader_v1',
 'leader_region_selector': 'dd.ldname a',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
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


def clean_parts(html: str) -> list[str]:
    text = re.sub(r"<[^>]+>", "\n", html)
    return [re.sub(r"\s+", " ", part).strip() for part in text.splitlines() if re.sub(r"\s+", "", part)]


def extract_duty_from_detail(detail_html: str, name: str, organization: str) -> tuple[str, str]:
    parts = clean_parts(detail_html)
    normalized_name = name.replace(" ", "")
    for index, part in enumerate(parts):
        if part == "部门领导":
            for cursor in range(index + 1, min(index + 6, len(parts) - 1)):
                if parts[cursor].replace(" ", "") == normalized_name:
                    duty = parts[cursor + 1].strip()
                    if not duty.startswith(organization) and not duty.startswith("辽宁省"):
                        duty = f"{organization}{duty}"
                    evidence = f"{parts[index]}；{parts[cursor]}；{parts[cursor + 1]}"
                    return duty, evidence
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析辽宁省应急管理厅领导列表及在线详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    for link in soup.select("dd.ldname a"):
        name = link.get_text("", strip=True).replace(" ", "")
        href = link.get("href", "")
        if not name or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_html = response.text
        except requests.RequestException:
            continue
        duty, evidence = extract_duty_from_detail(detail_html, name, organization)
        if not duty:
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
                "selector_summary": "dd.ldname a + 在线详情页部门领导/姓名/职务片段",
            }
        )
    return rows


if __name__ == "__main__":
    main()

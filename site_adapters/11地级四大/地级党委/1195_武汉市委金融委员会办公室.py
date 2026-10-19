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

PAGE_RULE = {'rule_id': '1195',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_wuhan_finance_leader_detail_v1',
 'leader_region_selector': '.ldxx-li',
 'name_selector': 'h3',
 'duty_selector': '',
 'detail_link_selector': 'a.ldxx-details[href]',
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
                     },
 'risk_flag': '列表页仅显示姓名，现任职务从当前人物详情页简介块提取',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldxx-li',
                     'name_selector': 'h3',
                     'duty_selector': '',
                     'detail_link_selector': 'a.ldxx-details[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'current_online_page',
                           'verified_status': 'verified_online_detail',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def fetch_detail_html(url: str) -> tuple[str, str]:
    """使用项目统一请求器抓取人物详情页。"""
    from crawler_core.fetcher import fetch_by_requests

    result = fetch_by_requests(url)
    return result.html, result.final_url


def extract_duty(html: str) -> str:
    """仅在当前人物详情页的简历正文块中定位完整现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    resume = soup.select_one(".ldxx_detail_resume_content")
    if resume is None:
        return ""
    text = clean_text(resume.get_text(" ", strip=True))
    match = re.search(r"现任([^。]+)", text)
    if not match:
        return ""
    duty = clean_text(match.group(1)).strip(" ：:，,。")
    if not re.search(r"书记|主任|局长", duty):
        return ""
    return duty


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for card in soup.select(".ldxx-li"):
        name_node = card.select_one("h3")
        link = card.select_one("a.ldxx-details[href]")
        if name_node is None or link is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            detail_html, detail_url = fetch_detail_html(detail_url)
            duty = extract_duty(detail_html)
        except Exception:
            continue
        if not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": str(rule.get("organization", "")),
                "url": base_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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

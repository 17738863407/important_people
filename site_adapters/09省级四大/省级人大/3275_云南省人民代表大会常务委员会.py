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

PAGE_RULE = {'rule_id': '3275',
 'domain': 'www.ynrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'yunnan_people_congress_leader_detail_v1',
 'leader_region_selector': 'a[href*="/srdcwhzrhyzcry_"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href*="/srdcwhzrhyzcry_"]',
                     'detail_name_selector': 'dl dd',
                     'detail_duty_selector': 'dl dt p strong',
                     'detail_content_selector': 'dl',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'a[href*="/srdcwhzrhyzcry_"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线人大概览列姓名，人物详情页个人信息栏提供职务字段'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'fixed_verified',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """云南省人大常委会主任会议组成人员详情页个人信息栏列姓名和职务。"""
    source_url = str(final_url or page_rule["url"])
    parser = str(page_rule["parser"])
    selector_summary = "人大概览人物链接 + 详情页dl中dd姓名和职务strong字段"
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    try:
        entry_response = session.get(source_url, timeout=30)
        entry_response.raise_for_status()
        soup = BeautifulSoup(entry_response.content, "html.parser")
    except requests.RequestException:
        soup = BeautifulSoup(html or "", "html.parser")
    for link in soup.select('a[href*="/srdcwhzrhyzcry_"]'):
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        if not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            continue
        detail_soup = BeautifulSoup(response.content, "html.parser")
        detail_box = next(
            (
                box
                for box in detail_soup.select("dl")
                if any(
                    "职务" in item.get_text("", strip=True).replace("\u2003", "")
                    for item in box.select("dt p, dt div")
                )
            ),
            None,
        )
        if not detail_box:
            continue
        name_node = detail_box.select_one("dd")
        name = "".join((name_node.get_text(" ", strip=True) if name_node else "").split())
        duty = ""
        for paragraph in detail_box.select("dt p, dt div"):
            raw_text = " ".join(paragraph.get_text(" ", strip=True).split())
            if re.match(r"^职[\s\u2003]*务[：:]", raw_text):
                duty = re.sub(r"^职[\s\u2003]*务[：:]\s*", "", raw_text).strip()
                break
        if not name or not duty:
            continue
        rows.append(
            {
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": parser,
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

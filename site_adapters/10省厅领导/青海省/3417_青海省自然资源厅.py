from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3417',
 'domain': 'zrzyt.qinghai.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'qinghai_natural_resources_leader_list_v1',
 'leader_region_selector': 'div#content > div.mainContent:nth-of-type(5) > div.mainBox > div.mBd:nth-of-type(2) > '
                           'ul.leaderList',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#content > div.mainContent:nth-of-type(5) > div.mainBox > '
                                               'div.mBd:nth-of-type(2) > ul.leaderList',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导之窗条目直接包含姓名、职务和简介现任句'}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按原领导之窗区域和条目顺序在线解析姓名、职务及真实详情页。"""
    organization = str(page_rule["organization"])
    source_url = str(page_rule["url"])
    parser = str(page_rule["parser"])
    selector_summary = "ul.leaderList a姓名+p.job职务+简介现任句"
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None and "window.location.href" in html:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        first_response = session.get(source_url, timeout=25, verify=False)
        first_response.raise_for_status()
        redirect_match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)", first_response.text)
        if redirect_match:
            verified_url = urljoin(source_url, redirect_match.group(1))
            verified_response = session.get(verified_url, timeout=25, verify=False)
            verified_response.raise_for_status()
            soup = BeautifulSoup(verified_response.text, "html.parser")
            region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        raise RuntimeError("未定位到原领导之窗 ul.leaderList 区域")

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in region.find_all("li", recursive=False):
        name_node = item.select_one("div.con h3.title > a[href]")
        duty_node = item.select_one("div.con h3.title > p.job")
        if name_node is None:
            continue
        name = " ".join(name_node.get_text(" ", strip=True).split())
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if not name:
            continue
        href = str(name_node.get("href") or "").strip()
        detail_url = urljoin(final_url or source_url, href) if href else ""
        parsed_detail = urlparse(detail_url)
        if (
            not detail_url
            or parsed_detail.scheme not in {"http", "https"}
            or parsed_detail.netloc != urlparse(source_url).netloc
            or "/gk/fdzdgknr/tld/content_" not in parsed_detail.path
        ):
            detail_url = ""
        key = (name, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": organization,
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

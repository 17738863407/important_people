from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '1788',
 'domain': 'mzt.nmg.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'neimenggu_mzt_leader_detail_colleagues_v1',
 'leader_region_selector': '.ldxx_box .cout, .ldxx_ts li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
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
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'div#mobile_main > div.index_mobile > '
                                               'div.content.clearfix:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析内蒙古自治区民政厅厅领导详情页及同事列表。"""
    from crawler_core.models import PersonRecord

    content_url = final_url
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one(".ldxx_box .cout"):
        redirect_hrefs = re.findall(
            r"window\.location\.replace\(\s*['\"]([^'\"]+)",
            html,
        )
        if redirect_hrefs:
            content_url = urljoin(final_url, redirect_hrefs[-1])
            response = requests.get(
                content_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
    records = []
    seen_names: set[str] = set()

    def add_record(name: str, duty: str, href: str, selector_summary: str) -> None:
        name = _clean_text(name)
        duty = _clean_text(duty)
        if not name or not duty or name in seen_names:
            return
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            return
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=urljoin(content_url, href) if href else "",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=selector_summary,
            )
        )

    current = soup.select_one(".ldxx_box .cout")
    if current:
        name_node = current.select_one("h2")
        duty_node = current.select_one("span")
        if name_node and duty_node:
            add_record(
                name_node.get_text(" ", strip=True),
                duty_node.get_text(" ", strip=True),
                content_url,
                "section=.ldxx_box .cout; name=h2; duty=span",
            )

    for item in soup.select(".ldxx_ts li"):
        link = item.select_one("a[title]")
        duty_node = item.select_one("span")
        if link and duty_node:
            add_record(
                link.get("title") or link.get_text(" ", strip=True),
                duty_node.get_text(" ", strip=True),
                link.get("href", ""),
                "section=.ldxx_ts; item=li; name=a[title]; duty=span",
            )

    return records


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

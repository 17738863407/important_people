from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1776',
 'domain': 'mzt.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'parser': 'fujian_mzt_leader_sidebar_v1',
 'leader_region_selector': '.leader_name_list li a',
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
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap:nth-of-type(1) > div.main:nth-of-type(3) > '
                                               'div.content.mar_t_large > div.row.content_bg_02 > div:nth-of-type(2) > '
                                               'div.trt-row.trt-row-large:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用在线列表详情链接解析'}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _fetch_html(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text, response.url


def _discover_current_leader_page(source_url: str) -> tuple[str, str]:
    """从同站首页动态发现领导栏目，并跟随栏目元刷新。"""
    parts = urlsplit(source_url)
    home_url = f"{parts.scheme or 'https'}://{parts.netloc}/"
    home_html, home_final_url = _fetch_html(home_url)
    home = BeautifulSoup(home_html, "html.parser")
    leader_link = next(
        (link for link in home.select("a[href]") if _clean_text(link.get_text(" ", strip=True)) == "领导之窗"),
        None,
    )
    if leader_link is None:
        raise RuntimeError("同站首页未发现领导之窗链接")
    leader_url = urljoin(home_final_url, str(leader_link.get("href", "")))
    leader_html, leader_final_url = _fetch_html(leader_url)
    leader = BeautifulSoup(leader_html, "html.parser")
    meta = leader.select_one('meta[http-equiv="refresh"], meta[http-equiv="Refresh"]')
    if meta:
        match = re.search(r"url\s*=\s*([^;]+)$", str(meta.get("content", "")), re.IGNORECASE)
        if match:
            leader_html, leader_final_url = _fetch_html(urljoin(leader_final_url, match.group(1).strip()))
    return leader_html, leader_final_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省民政厅领导之窗侧栏。"""
    if not html:
        html, final_url = _discover_current_leader_page(str(page_rule.get("url", "")))
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    source_url = final_url or str(page_rule.get("url", ""))

    for link in soup.select(".leader_name_list li a"):
        name_node = link.select_one("span")
        duty_node = link.select_one("p")
        if not name_node or not duty_node:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not name or not duty or name in seen_names:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue

        seen_names.add(name)
        href = str(link.get("href") or "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip("/") != str(page_rule.get("url", "")).rstrip("/"):
                detail_url = candidate_url
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "section=.leader_name_list; item=li a; name=span; duty=p",
            }
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

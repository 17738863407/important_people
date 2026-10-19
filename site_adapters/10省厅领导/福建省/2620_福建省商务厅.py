from __future__ import annotations

import sys
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

PAGE_RULE = {'rule_id': '2620',
 'domain': 'swt.fj.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_fujian_commerce_tabs_leader_cards_v1',
 'leader_region_selector': '.tabs_content .leader_pic, .tabs_content .leader_name_list li',
 'name_selector': '.leader_pic h3, li span',
 'duty_selector': '.leader_pic p, li p',
 'detail_link_selector': '.tabs_content a[href*="/stld/"], .tabs_content a[href*="../xxgk/stld/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.tabs_content .leader_pic, .tabs_content .leader_name_list li',
                     'name_selector': '.leader_pic h3, li span',
                     'duty_selector': '.leader_pic p, li p',
                     'detail_link_selector': '.tabs_content a[href*="/stld/"], .tabs_content a[href*="../xxgk/stld/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _clean_name(value: str) -> str:
    text = _clean_text(value)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省商务厅机构职能页省厅领导模块。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    top = soup.select_one(".tabs_content .leader_pic")
    if top:
        name_node = top.select_one("h3")
        duty_node = top.select_one("p")
        link = top.select_one('a[href*="/stld/"], a[href*="../xxgk/stld/"]')
        name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if name and duty:
            detail_url = urljoin(final_url, link.get("href", "")) if link else ""
            if detail_url.rstrip("/") == final_url.rstrip("/"):
                detail_url = ""
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "source_url": final_url,
                    "parser": page_rule.get("parser", ""),
                    "selector_summary": "strategy=css；leader=.tabs_content leader cards；name=h3/span；duty=p；detail=a[href*=stld]；api_enabled=False",
                }
            )
            seen.add((name, duty, detail_url))

    for item in soup.select(".tabs_content .leader_name_list li"):
        name_node = item.select_one("span")
        duty_node = item.select_one("p")
        link = item.select_one("a[href]")
        name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not name or not duty:
            continue
        detail_url = urljoin(final_url, link.get("href", "")) if link else ""
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "source_url": final_url,
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=.tabs_content leader cards；name=h3/span；duty=p；detail=a[href*=stld]；api_enabled=False",
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

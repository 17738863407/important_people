from __future__ import annotations

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

PAGE_RULE = {'rule_id': '2578',
 'domain': 'sthjt.sc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_sichuan_ecology_p_ldgl_cards_v1',
 'leader_region_selector': '.p_ldgl .cont, .p_ldgl .ld_list li',
 'name_selector': '.cont h3, h4 a',
 'duty_selector': '.ld_tz, li > span',
 'detail_link_selector': '.p_ldgl a[href*="ld"], .p_ldgl a[href*="newldxq"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.p_ldgl .cont, .p_ldgl .ld_list li',
                     'name_selector': '.cont h3, h4 a',
                     'duty_selector': '.ld_tz, li > span',
                     'detail_link_selector': '.p_ldgl a[href*="ld"], .p_ldgl a[href*="newldxq"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'online_page', 'verified_status': 'verified', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析四川省生态环境厅领导简介模块。"""
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".p_ldgl")
    if not box:
        return []
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    top_duty_node = box.select_one(".ld_tz")
    top_name_node = box.select_one(".cont h3")
    top_link = box.select_one(".cont a[href]") or box.select_one(".pic a[href]")
    if top_duty_node and top_name_node:
        name = _clean_text(top_name_node.get_text(" ", strip=True))
        duty = _clean_text(top_duty_node.get_text(" ", strip=True))
        detail_url = urljoin(final_url, top_link.get("href", "")) if top_link else ""
        if name and duty:
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "source_url": final_url,
                    "parser": page_rule.get("parser", ""),
                    "selector_summary": "strategy=css；leader=.p_ldgl；name=.cont h3/h4 a；duty=.ld_tz/li>span；detail=a[href]；api_enabled=False",
                }
            )
            seen.add((name, duty, detail_url))

    for item in box.select(".ld_list li"):
        duty_node = item.select_one(":scope > span")
        name_node = item.select_one("h4 a")
        link = name_node if name_node and name_node.has_attr("href") else item.select_one("a[href]")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not name or not duty:
            continue
        detail_url = urljoin(final_url, link.get("href", "")) if link else ""
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
                "selector_summary": "strategy=css；leader=.p_ldgl；name=.cont h3/h4 a；duty=.ld_tz/li>span；detail=a[href]；api_enabled=False",
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

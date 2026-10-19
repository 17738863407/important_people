from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1890',
 'domain': 'www.news.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinhua_part_leader_cards_v1',
 'leader_region_selector': '#part-leader-box .part-leader-list-item',
 'name_selector': '.part-leader-list-title',
 'duty_selector': '.part-leader-list-title span',
 'detail_link_selector': '',
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
 'locator': {'css': {'leader_region_selector': '#part-leader-box .part-leader-list-item',
                     'name_selector': '.part-leader-list-title',
                     'duty_selector': '.part-leader-list-title span',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified_online', 'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新华通讯社领导介绍卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for item in soup.select("#part-leader-box .part-leader-list-item"):
        title_el = item.select_one(".part-leader-list-title")
        duty_el = item.select_one(".part-leader-list-title span")
        if title_el is None or duty_el is None:
            continue
        duty = duty_el.get_text(" ", strip=True).strip("（）()")
        name_text = title_el.get_text(" ", strip=True).replace(duty_el.get_text(" ", strip=True), "")
        name = "".join(name_text.split())
        if not name or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
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

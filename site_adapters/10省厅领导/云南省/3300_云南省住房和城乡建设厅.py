from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3300',
 'domain': 'zfcxjst.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': 'yn_housing_leader_item_v2',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_card_yn_housing_leader_v2',
 'leader_region_selector': 'a.leader-item',
 'name_selector': '.name',
 'duty_selector': '.post',
 'detail_link_selector': 'a.leader-item[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'card_link',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '只读取厅领导页的 leader-item 卡片，姓名、职务和独立人物链接均取卡片明确字段',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a.leader-item',
                     'name_selector': '.name',
                     'duty_selector': '.post',
                     'detail_link_selector': 'a.leader-item[href]',
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析云南省住房和城乡建设厅厅领导卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    cards = soup.select(page_rule["leader_region_selector"])
    if not cards:
        raise RuntimeError("厅领导页面未找到 leader-item 卡片")
    for card in cards:
        name_node = card.select_one(page_rule["name_selector"])
        duty_node = card.select_one(page_rule["duty_selector"])
        if not name_node or not duty_node:
            continue
        name = re.sub(r"[\s\u00a0\u3000]+", "", name_node.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        duty = re.sub(r"[\s\u00a0\u3000]+", "", duty_node.get_text("", strip=True))
        if not duty or organization not in duty:
            continue
        seen.add(name)
        detail_url = urljoin(base_url, card.get("href", ""))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                # 姓名、职务均来自当前卡片明确字段。
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "a.leader-item 卡片 .name 姓名 + .post 职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()

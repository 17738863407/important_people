from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1139',
 'domain': 'www.jiangsu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_jiangsu_gov_leader_group_v1',
 'leader_region_selector': '.ld-left .ld-205',
 'name_selector': '.ld-xx-name',
 'duty_selector': '.ld-zw',
 'detail_link_selector': '.ld-xx a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.ld-left .ld-205',
                     'name_selector': '.ld-xx-name',
                     'duty_selector': '.ld-zw',
                     'detail_link_selector': '.ld-xx a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染后的省政府领导分组已在 DOM 中完整呈现'},
             'migration': {'source': 'last_batch_online_template+manual_dom_refine',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    current_duty = ""
    for group in soup.select(".ld-left .ld-205"):
        raw_duty = clean_text(group.select_one(".ld-zw").get_text(" ", strip=True)) if group.select_one(".ld-zw") else ""
        duty = re.sub(r"\s+", "", raw_duty)
        if duty:
            current_duty = duty
        else:
            duty = current_duty
        if duty not in {"省长", "副省长", "秘书长"}:
            continue
        for link in group.select(".ld-xx a[href]"):
            name_node = link.select_one(".ld-xx-name")
            name = clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
            name = re.sub(r"\s+", "", name)
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(page_rule["url"], link.get("href", "")),
                    "evidence": duty,
                    "selector_summary": ".ld-left .ld-205 职务分组+姓名链接",
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

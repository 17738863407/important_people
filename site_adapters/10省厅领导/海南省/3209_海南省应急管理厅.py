from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3209',
 'domain': 'yjglt.hainan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_text_hainan_emergency_leader_v1',
 'leader_region_selector': '厅领导信息文本段',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
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
    """解析海南省应急管理厅领导信息文本段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    parts = [re.sub(r"\s+", " ", item).strip() for item in soup.get_text("\n", strip=True).splitlines()]
    parts = [item for item in parts if item]
    try:
        start = parts.index("厅领导信息") + 1
    except ValueError:
        return []
    end = len(parts)
    for index in range(start, len(parts)):
        if parts[index].startswith("二、省应急管理厅") or parts[index] == "基本信息":
            end = index
            break
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    cursor = start
    while cursor + 1 < end:
        name = parts[cursor]
        duty_core = parts[cursor + 1]
        duty_core = duty_core.replace("（兼）", "").replace("(兼)", "").replace("（挂职）", "").replace("(挂职)", "")
        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) and ("厅长" in duty_core or "巡视员" in duty_core) and name not in seen:
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty_core,
                    "detail_url": "",
                    "evidence": duty_core,
                    "parser": page_rule["parser"],
                    "selector_summary": "厅领导信息段姓名/职务相邻行",
                }
            )
            cursor += 2
            continue
        cursor += 1
    return rows


if __name__ == "__main__":
    main()

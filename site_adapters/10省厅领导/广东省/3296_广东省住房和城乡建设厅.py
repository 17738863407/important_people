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

PAGE_RULE = {'rule_id': '3296',
 'domain': 'zfcxjst.gd.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_anchor_gd_housing_leader_v1',
 'leader_region_selector': 'a[href^="#leader_"]',
 'name_selector': 'a[href^="#leader_"] b',
 'duty_selector': 'a[href^="#leader_"] 文本中 b 前职务',
 'detail_link_selector': 'a[href^="#leader_"]',
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
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a[href^="#leader_"]',
                     'name_selector': 'a[href^="#leader_"] b',
                     'duty_selector': 'a[href^="#leader_"] 文本中 b 前职务',
                     'detail_link_selector': 'a[href^="#leader_"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
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
    """解析广东省住房和城乡建设厅领导信息锚点列表。"""
    from html import unescape

    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    pattern = re.compile(
        r'<a\s+href="(?P<href>#leader_[^"]+)">(?P<duty>.*?)<b>(?P<name>[^<]+)</b>',
        re.I | re.S,
    )
    for match in pattern.finditer(html):
        name = re.sub(r"[\s\u00a0\u3000]+", "", unescape(match.group("name")))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        duty = re.sub(r"<[^>]+>", "", match.group("duty"))
        duty = re.sub(r"[\s\u00a0\u3000]+", "", unescape(duty)).strip(" ：:")
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": '原始HTML a[href="#leader_"] b 姓名及前置职务',
            }
        )
    return rows


if __name__ == "__main__":
    main()

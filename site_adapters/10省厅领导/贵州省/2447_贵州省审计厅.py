from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2447',
 'domain': 'sjt.guizhou.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': 'html > body.ScrollStyle > div.warp > div.main:nth-of-type(2) > div.ldzc:nth-of-type(2)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body.ScrollStyle > div.warp > div.main:nth-of-type(2) > '
                                               'div.ldzc:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list:
    """保留详情链的动态人物提取，仅清理当前人物的原始职务依据。"""
    from crawler_core.detail_links import parse_detail_chain_records
    from crawler_core.settings import get_settings

    records = parse_detail_chain_records(
        page_rule,
        html,
        final_url,
        None,
        get_settings().request_timeout_seconds,
    )
    for record in records:
        source = re.sub(r"\s+", " ", str(record.evidence or "")).strip()
        current_match = re.search(r"现任\s*([^。]+)", source)
        if current_match:
            evidence = current_match.group(1)
        else:
            evidence = re.sub(rf"^\s*{re.escape(record.name)}\s*", "", source)
        record.evidence = re.sub(r"\s*([、，,])\s*", r"\1", evidence).strip(" ，,。；;：: ")
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

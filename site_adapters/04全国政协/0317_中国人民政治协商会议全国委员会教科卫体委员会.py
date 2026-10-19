from __future__ import annotations

import sys
from pathlib import Path
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '0317',
 'domain': 'www.cppcc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': 'cppcc_role_group',
 'reuse_scope': 'page_structure',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'S019_cppcc_main_role_group_v1',
 'leader_region_selector': '.zhengxie17370_shipinji_ind03_1214',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.zhengxie17370_shipinji_ind03_1214',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置；本次迁移保留旧定位字段，后续逐页接口探测', 'probe_status': '需要逐页探测'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'success_dir', 'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """复用公共政协分组解析，仅将依据说明限定为已解析职务。"""
    import re

    from crawler_core.parser_registry import parse_with_registered_parser

    records = parse_with_registered_parser(page_rule, html, final_url, None)
    records = [record for record in records if str(record.duty or "").strip() != "委员"]
    for record in records:
        raw_evidence = str(record.evidence or "")
        evidence = str(record.duty or "").strip()
        if re.search(r"[（(][^）)]*驻会[^）)]*[）)]", raw_evidence):
            evidence = f"{evidence}（驻会）"
        record.evidence = evidence
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




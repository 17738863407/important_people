from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2354',
 'domain': 'www.shandong.gov.cn',
 'page_type': '人物表格页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'S006_shandong_gov_ldxx_table_v1',
 'source_parser': 'shandong_department_ldxx_parser_v1',
 'leader_region_selector': '#con-one-2, .ldxx_con',
 'name_selector': '.ldxx_name',
 'duty_selector': '.ldxx_zw',
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
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """沿用山东省部门领导表格解析，仅规范业务字段与详情链接。"""
    from crawler_core.parsers_v1 import shandong_department_ldxx_parser_v1

    return [
        {
            "name": row.name,
            "duty": row.duty,
            "detail_url": "",
            "evidence": row.duty,
            "confidence": row.confidence,
            "parser": "S006_shandong_gov_ldxx_table_v1",
            "selector_summary": "leader=#con-one-2, .ldxx_con；name=.ldxx_name；duty=.ldxx_zw",
        }
        for row in shandong_department_ldxx_parser_v1(page_rule, html, final_url)
    ]


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

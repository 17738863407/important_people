from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3342',
 'domain': 'www.zj.gov.cn',
 'page_type': '人物列表完整页',
 'load_mode': '接口数据加载',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'S002_zhejiang_gov_leader_group_v1',
 'source_parser': 'zhejiang_government_leader_group_parser_v1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'div.list_leader_b li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'person_name_link',
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复；已排除内设机构负责人混入风险',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list:
    """沿用浙江注册解析器，仅将网页分组职务规范为依据说明。"""
    from crawler_core.parsers_v1 import zhejiang_government_leader_group_parser_v1

    rows = zhejiang_government_leader_group_parser_v1(page_rule, html, final_url)
    for row in rows:
        row.evidence = row.duty
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

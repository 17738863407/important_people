from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造仅包含技术定位信息的页面规则。"""
    return {'rule_id': rule_id,
 'domain': 'www.court.gov.cn',
 'page_type': '人物表格页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'court_text_duty_name_parser_v1',
 'source_parser': 'court_text_duty_name_parser_v1',
 'leader_region_selector': '.txt_txt',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list:
    """沿用原法院正文解析器，仅将网页原始职务映射到依据说明。"""
    import re

    from bs4 import BeautifulSoup
    from crawler_core.parsers_v1 import court_text_duty_name_parser_v1

    rows = court_text_duty_name_parser_v1(page_rule, html, final_url)
    for row in rows:
        row.evidence = row.duty

    region = BeautifulSoup(html, "html.parser").select_one(".txt_txt")
    if region is None:
        return rows
    page_text = re.sub(r"\s+", "", region.get_text("", strip=True))
    indexed_rows = list(enumerate(rows))
    indexed_rows.sort(
        key=lambda item: (
            page_text.find(re.sub(r"\s+", "", item[1].name))
            if page_text.find(re.sub(r"\s+", "", item[1].name)) >= 0
            else len(page_text) + item[0]
        )
    )
    return [row for _, row in indexed_rows]


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "0281"
    main(rule_id_value)

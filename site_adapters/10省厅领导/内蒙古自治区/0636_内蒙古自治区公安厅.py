from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0636',
 'domain': 'gat.nmg.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V008_text_name_nextline_duty_v1',
 'leader_region_selector': 'html > body > div.xxgkk:nth-of-type(2) > div.xxgkzn:nth-of-type(2) > '
                           'div.xxgkznk:nth-of-type(2) > div.xxgknr-nrt:nth-of-type(3) > div.gat_ld2.block_lh_24',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': "a[href*='ld']",
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
 'locator': {'css': {'leader_region_selector': 'html > body > div.xxgkk:nth-of-type(2) > div.xxgkzn:nth-of-type(2) > '
                                               'div.xxgkznk:nth-of-type(2) > div.xxgknr-nrt:nth-of-type(3) > '
                                               'div.gat_ld2.block_lh_24',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': "a[href*='ld']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """复用V008结果，精确移除当前姓名并补取同一人物节点内被截断的职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.parsers_v1 import name_nextline_duty_parser_v1

    records = name_nextline_duty_parser_v1(page_rule, html, final_url, None)
    soup = BeautifulSoup(html, "html.parser")
    node_duties: dict[str, str] = {}
    for link in soup.select("a.txtlink[title]"):
        name = str(link.get("title") or "").strip()
        duty_parts = ["".join(paragraph.stripped_strings).strip() for paragraph in link.select("div p")]
        duty_parts = [part for part in duty_parts if part]
        if name and duty_parts:
            node_duties[name] = "，".join(duty_parts)

    for record in records:
        if record.evidence == f"{record.name} {record.duty}":
            record.evidence = record.duty
        if record.evidence.endswith(("、", "，", ",", "；", ";")):
            complete_duty = node_duties.get(record.name, "")
            prefix = record.evidence.rstrip("、，,；;")
            if complete_duty.startswith(prefix) and not complete_duty.endswith(("、", "，", ",", "；", ";")):
                record.evidence = complete_duty
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

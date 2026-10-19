from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0787',
 'domain': 'gxt.jiangxi.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'online_jx_gxt_table_line_pairs_v1',
 'leader_region_selector': 'html > body > table:nth-of-type(3)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '现任与历任经历混合，需限定姓名下一行职务',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > table:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线 DOM 领导表格姓名下一行职务解析'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导表格中姓名下一行的现任职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    leader_region = soup.select_one("html > body > table:nth-of-type(3)") or soup
    lines = [line.strip() for line in leader_region.get_text("\n", strip=True).splitlines() if line.strip()]
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, line in enumerate(lines[:-1]):
        name = re.sub(r"[\s\u3000\xa0]+", "", line)
        duty = re.sub(r"[\s\u3000\xa0]+", "", lines[index + 1])
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or name in seen
            or not re.fullmatch(r"(?:党组书记、厅长|党组成员、副厅长|一级巡视员|二级巡视员|总工程师)", duty)
        ):
            continue
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": parser,
                "selector_summary": "正文表格纯文本行：姓名下一行为职务",
            }
        )
        seen.add(name)

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

from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3386',
 'domain': 'zjt.qinghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_qinghai_housing_leader_cards_v2',
 'leader_region_selector': '.leaderzconelist, .leaderzcerlist',
 'name_selector': 'a > p > span:nth-of-type(1)',
 'duty_selector': 'a > p > span:nth-of-type(2)',
 'detail_link_selector': '.leaderzconelist > a[href], .leaderzcerlist > a[href]',
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
 'risk_flag': '党组书记和厅长使用leaderzconelist，其余领导使用leaderzcerlist，须合并并保持DOM顺序',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leaderzconelist, .leaderzcerlist',
                     'name_selector': 'a > p > span:nth-of-type(1)',
                     'duty_selector': 'a > p > span:nth-of-type(2)',
                     'detail_link_selector': '.leaderzconelist > a[href], .leaderzcerlist > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False,
                     'reason': '现行静态领导之窗直接提供完整领导卡片'},
             'migration': {'source': 'sequential_static_html_builder',
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
    """解析青海省住房和城乡建设厅领导卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".leaderzconelist, .leaderzcerlist"):
        link = card.select_one(":scope > a[href]")
        fields = link.select("p > span") if link else []
        if link is None or len(fields) < 2:
            continue
        name = re.sub(r"[\s\u00a0\u3000]+", "", fields[0].get_text("", strip=True))
        name = re.sub(r"（.*?）|\(.*?\)", "", name)
        duty = re.sub(r"[\s\u00a0\u3000]+", "", fields[1].get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty:
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "leaderzconelist/leaderzcerlist卡片；p内第一span姓名、第二span职务",
            }
        )

    if rows:
        return rows

    return rows


if __name__ == "__main__":
    main()

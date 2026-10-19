from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2958',
 'domain': 'wlt.shanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V004_card_person_v1',
 'leader_region_selector': 'html > body > div.centent:nth-of-type(5) > div.centent > div.main:nth-of-type(2) > '
                           'div.main-l:nth-of-type(1) > div.lingdao2:nth-of-type(3)',
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
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.centent:nth-of-type(5) > div.centent > '
                                               'div.main:nth-of-type(2) > div.main-l:nth-of-type(1) > '
                                               'div.lingdao2:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", " ", text)
    text = re.sub(r"\s+([，。、；：（）])", r"\1", text)
    text = re.sub(r"([，、])\s+", r"\1", text)
    return text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析山西省文化和旅游厅领导信息直出列表。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(".lingdao1, .lingdao2")
    rows: list[dict[str, str]] = []
    for region in regions:
        for link in region.select("a[href]"):
            text = clean_text(link.get_text(" ", strip=True))
            match = re.fullmatch(r"(?P<name>[\u4e00-\u9fa5]{2,3})\s+(?P<duty>(?:厅|省|二级).+)", text)
            if match is None:
                continue
            rows.append(
                {
                    "name": clean_text(match.group("name")),
                    "duty": "",
                    "detail_url": urljoin(final_url, link.get("href", "")),
                    "evidence": clean_text(match.group("duty")),
                    "parser": "page_inline_shanxi_wlt_leader_text_v1",
                    "selector_summary": "region=.lingdao1,.lingdao2；pattern=姓名 职务",
                    "order": str(len(rows) + 1),
                }
            )
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

from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0948',
 'domain': 'www.hebei.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hebei_gov_office_single_profile_v1',
 'leader_region_selector': 'html#-am-page > body > div.pcys:nth-of-type(1)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '旧规则按详情链遍历全页链接，误抓导航正文；该页为单人物详情页，改为直接解析正文',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html#-am-page > body > div.pcys:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '页面正文已直接包含单人物现任职务'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩详情页正文空白。"""
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河北省人民政府办公厅单人物领导简介。"""
    soup = BeautifulSoup(html, "html.parser")
    profile = soup.select_one(".art_jjall")
    name_node = profile.select_one(".jjname1") if profile else None
    content_node = profile.select_one("#jjconN") if profile else None
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
    content = clean_text(content_node.get_text(" ", strip=True) if content_node else "")
    match = re.search(r"(现任[^。]*。)", content)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not match:
        return []
    current_sentence = match.group(1)
    duty = current_sentence.removeprefix("现任").rstrip("。")
    return [
        {
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "strategy=custom_parse_page；name=.jjname1；pattern=现任[^。]*。",
        }
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

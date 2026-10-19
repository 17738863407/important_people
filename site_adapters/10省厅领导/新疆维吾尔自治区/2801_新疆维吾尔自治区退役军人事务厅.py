from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2801',
 'domain': 'tyjr.xinjiang.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_xinjiang_veterans_merged_profile_v1',
 'leader_region_selector': 'body',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" ：，。;；")


def _clean_name(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/tyjr/ldxx/"]'):
        name = _clean_name(link.get("title") or link.get_text(" ", strip=True))
        paragraph = link.find_next_sibling("p")
        text = _clean_text(paragraph.get_text(" ", strip=True) if paragraph else "")
        current = re.search(r"现任自治区退役军人事务厅[^。]*(?:。|$)", text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not current or name in seen:
            continue
        seen.add(name)
        current_sentence = current.group(0).rstrip("。")
        duty = current_sentence.removeprefix("现任自治区退役军人事务厅")
        evidence = re.sub(
            r"^现任(?:职务)?[：:]?\s*",
            "",
            current_sentence,
            count=1,
        )
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href", "")),
                "evidence": evidence,
                "parser": "custom_xinjiang_veterans_merged_profile_v1",
                "selector_summary": "领导信息a[href*=tyjr/ldxx]+相邻p现任职务句",
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

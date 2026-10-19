from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2063',
 'domain': 'oc.hainan.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'hainan_ocean_leader_info_v1',
 'leader_region_selector': '.ldjsxin .ldjsxin-ty',
 'name_selector': '.ldjsxin-ty-r h3 a',
 'duty_selector': '.ldjsxin-ty-r h4 a',
 'detail_link_selector': '.ldjsxin-ty-r h3 a[href]',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldjsxin .ldjsxin-ty',
                     'name_selector': '.ldjsxin-ty-r h3 a',
                     'duty_selector': '.ldjsxin-ty-r h4 a',
                     'detail_link_selector': '.ldjsxin-ty-r h3 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析领导信息合并页中的姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    if not soup.select(".ldjsxin .ldjsxin-ty"):
        import requests

        response = requests.get(page_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".ldjsxin .ldjsxin-ty"):
        name_link = item.select_one(".ldjsxin-ty-r h3 a")
        duty_link = item.select_one(".ldjsxin-ty-r h4 a")
        if name_link is None or duty_link is None:
            continue
        name = _clean_text(name_link.get_text(" ", strip=True))
        duty = _clean_text(duty_link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(page_url, str(name_link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
            }
        )
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

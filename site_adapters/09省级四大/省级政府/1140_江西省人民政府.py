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

PAGE_RULE = {'rule_id': '1140',
 'domain': 'www.jiangxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_jiangxi_gov_grouped_leaders_v1',
 'leader_region_selector': '.tab-brief .leader',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.tab-brief .leader a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
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
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.tab-brief .leader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.tab-brief .leader a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染后的领导分组使用 CSS/HTML 定位解析'},
             'migration': {'source': 'legacy_page_rule',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for block in soup.select(".tab-brief .leader"):
        duty_node = block.select_one(".ldtit h2")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if duty not in {"省长", "副省长", "省政府党组成员", "秘书长"}:
            continue
        for link in block.select("ul li a[href]"):
            name = clean_text(link.get("title", "") or link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "organization": str(rule.get("organization", "")),
                    "url": base_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(base_url, link.get("href", "")),
                    "evidence": duty,
                    "confidence": "high",
                    "parser": str(rule.get("parser", "")),
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

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

PAGE_RULE = {'rule_id': '1030',
 'domain': 'www.hubei.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_hubei_gov_ld_block_v1',
 'leader_region_selector': '#b1 .ld_block',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '#b1 .ld_block .right a[href]',
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
 'locator': {'css': {'leader_region_selector': '#b1 .ld_block',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '#b1 .ld_block .right a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染后的领导块使用 CSS/HTML 定位解析'},
             'migration': {'source': 'legacy_page_rule',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for block in soup.select("#b1 .ld_block"):
        duty_node = block.select_one(".left h4")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if duty not in {"省长", "副省长", "秘书长"}:
            continue
        for item in block.select(".right li"):
            link = item.select_one("p a[href]") or item.select_one("a[href][title]")
            if not link:
                continue
            name = clean_text(link.get_text(" ", strip=True) or link.get("title", "")).replace(" ", "")
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

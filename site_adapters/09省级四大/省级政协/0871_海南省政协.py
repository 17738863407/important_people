from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0871',
 'domain': 'www.hainanzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hainan_cppcc_leader_groups_v1',
 'leader_region_selector': '.ldy',
 'name_selector': '.ldy-lm3 li a[title], .ldy-lm4 li a[title]',
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
 'risk_flag': '原规则仅有外层区域且缺少姓名/职务选择器，通用解析输出空行；需按政协领导分组解析',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldy',
                     'name_selector': '.ldy-lm3 li a[title], .ldy-lm4 li a[title]',
                     'duty_selector': '',
                     'detail_link_selector': 'li a[title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩海南省政协领导页文本空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析海南省政协领导分组列表。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".ldy")
    if root is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = final_url or str(page_rule.get("url", ""))
    selector_summary = "strategy=custom_parse_page；root=.ldy；duty=.ldy-lm2；names=后续.ldy-lm3/.ldy-lm4 li a[title]"

    for title_block in root.select(".ldy-lm2"):
        duty = clean_text(title_block.get_text(" ", strip=True))
        list_block = title_block.find_next_sibling()
        while isinstance(list_block, Tag):
            classes = set(list_block.get("class") or [])
            if classes & {"ldy-lm3", "ldy-lm4"}:
                break
            list_block = list_block.find_next_sibling()
        if not isinstance(list_block, Tag):
            continue

        for item in list_block.select("li a[title]"):
            name = clean_text(item.get("title") or item.get_text(" ", strip=True))
            if not name or not duty or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", "")) or source_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(source_url, str(item.get("href", ""))),
                    "evidence": duty,
                    "confidence": "high",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": selector_summary,
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

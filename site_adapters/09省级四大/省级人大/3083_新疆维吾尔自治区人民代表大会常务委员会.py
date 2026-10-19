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

PAGE_RULE = {'rule_id': '3083',
 'domain': 'www.xjpcsc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinjiang人大_leaders_v1',
 'leader_region_selector': '.xj-leader-container',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.xj-wrapper:nth-of-type(1)',
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


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def normalize_name(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"（[^）]*）|\([^)]*\)", "", text)
    return re.sub(r"\s+", "", text)


def valid_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fa5·]{2,20}", value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区人大常委会主任会议成员。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for subtitle in soup.select(".xj-leader-container .subtitle"):
        duty_label = clean_text(subtitle.get_text(" ", strip=True))
        if "主任" not in duty_label:
            continue
        duty = duty_label
        photos = subtitle.find_next_sibling("div", class_="photos")
        if not photos:
            continue
        for link in photos.select("a.cell[href]"):
            name = normalize_name((link.select_one(".desc") or link).get_text(" ", strip=True))
            if not valid_name(name) or name in seen:
                continue
            detail_url = urljoin(page_rule["url"], link.get("href", ""))
            if detail_url.rstrip("/") == page_rule["url"].rstrip("/"):
                detail_url = ""
            seen.add(name)
            rows.append(
                {
                    "organization": page_rule["organization"],
                    "url": page_rule["url"],
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "parser": "page_inline_xinjiang人大_leaders_v1",
                    "selector_summary": ".xj-leader-container subtitle分组 + photos a.cell",
                }
            )
    return rows


if __name__ == "__main__":
    main()

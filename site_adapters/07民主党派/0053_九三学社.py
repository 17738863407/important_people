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

PAGE_RULE = {'rule_id': '0053',
 'domain': 'www.93.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_93gov_chair_vice_chair_cards_v1',
 'leader_region_selector': 'div#c3.content.content2 li',
 'name_selector': 'h5',
 'duty_selector': 'h5',
 'detail_link_selector': 'div#c3.content.content2 li a[href]',
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
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div#c3.content.content2 li',
                     'name_selector': 'h5',
                     'duty_selector': 'h5',
                     'detail_link_selector': 'div#c3.content.content2 li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def split_name_duty(text: str) -> tuple[str, str]:
    """拆分“姓名+主席/副主席”等合写文本。"""
    compact = clean_text(text).replace(" ", "")
    match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8}?)(?P<duty>常务副主席|副主席|主席)", compact)
    if not match:
        return "", ""
    return match.group("name"), match.group("duty")


def is_hidden_node(node) -> bool:
    """判断节点是否位于隐藏 DOM 中。"""
    current = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(item).lower() for item in (current.get("class") or [])}
        if "display:none" in style or current.has_attr("hidden"):
            return True
        if str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if classes & {"hide", "hidden", "dn", "none"}:
            return True
        current = current.parent
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析九三学社主席、副主席卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    base_url = final_url or source_url
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in soup.select("div#c3.content.content2 li"):
        if is_hidden_node(item):
            continue
        title = item.select_one("h5")
        if title is None:
            continue
        name, duty = split_name_duty(title.get_text(" ", strip=True))
        if not name or not duty:
            continue
        link = item.select_one("a[href]")
        detail_url = urljoin(base_url, str(link.get("href") or "")) if link else ""
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
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

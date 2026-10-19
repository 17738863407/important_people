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

PAGE_RULE = {'rule_id': '0783',
 'domain': 'gxt.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_gxt_visible_leader_card_v1',
 'leader_region_selector': '.leader',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.leader p a[href]',
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
 'risk_flag': '原CSS定位到单一卡片且通用卡片解析为空；末尾卡片隐藏详情行姓名与可见姓名不一致，需以可见h2为准',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.leader p a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def compact_name(value: str) -> str:
    """清理姓名中的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河南省工业和信息化厅领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".leader"):
        title = card.select_one("h2")
        name_node = title.select_one("span") if title else None
        if not title or not name_node:
            continue
        name = compact_name(name_node.get_text(" ", strip=True))
        name_node.extract()
        duty = clean_text(title.get_text(" ", strip=True))
        detail_link = card.select_one("p a[href]")
        detail_url = urljoin(source_url, str(detail_link.get("href") or "")) if detail_link else ""
        if (
            name in seen
            or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not duty
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "order": len(rows) + 1,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".leader h2可见姓名和职务；详情链接仅作附加信息",
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

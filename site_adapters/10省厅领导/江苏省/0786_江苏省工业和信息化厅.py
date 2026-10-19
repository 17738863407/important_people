from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0786',
 'domain': 'gxt.jiangsu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_jiangsu_gxt_leader_card_prg1_v1',
 'leader_region_selector': '.rigt',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.rigt p.prg1 a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '原表格解析器用于卡片页导致空结果；当前页面已有机构领导卡片',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.rigt',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.rigt p.prg1 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """清理姓名中的排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江苏省工业和信息化厅机构领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".rigt"):
        prg_nodes = card.select("p.prg1")
        if len(prg_nodes) < 2:
            continue
        link = prg_nodes[0].select_one("a[href]")
        if not link:
            continue
        name = clean_name(link.get_text(" ", strip=True))
        duty = clean_text(prg_nodes[1].get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(source_url).netloc.lower()
        real_person_page = bool(re.search(r"/art/\d{4}/\d{1,2}/\d{1,2}/art_90962_\d+\.html$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        seen.add(name)
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
                "selector_summary": ".rigt卡片首个p.prg1取姓名链接，第二个p.prg1取职务",
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

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

PAGE_RULE = {'rule_id': '0788',
 'domain': 'gxt.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_jilin_gxt_tldfg_anchor_card_v1',
 'leader_region_selector': '.tldfg_c a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.tldfg_c a[href]',
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
 'risk_flag': '原卡片解析器无法识别.tldfg_c领导分工链接卡片',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.tldfg_c a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.tldfg_c a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_evidence(value: str) -> str:
    """仅删除独立“兼”状态标记，保留其前后的具体职务。"""
    return re.sub(r"(?:（兼）|\(兼\)|<兼>|＜兼＞)", "", clean_text(value)).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析吉林省工业和信息化厅领导分工卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".tldfg_c a[href]"):
        name_node = link.select_one("b")
        duty_node = link.select_one("p")
        if not name_node or not duty_node:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = clean_evidence(duty_node.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(source_url).netloc.lower()
        real_person_page = bool(re.search(r"/tldfg/[a-z0-9_-]+/$", urlparse(detail_url).path))
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
                "selector_summary": ".tldfg_c a内b取姓名，p取职务",
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

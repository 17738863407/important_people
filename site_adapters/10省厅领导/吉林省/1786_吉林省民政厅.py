from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1786',
 'domain': 'mzt.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'jilin_mzt_leader_list_2025_v1',
 'leader_region_selector': '.ldlb_20250312cs li a',
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
                     'max_detail_links': 50},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\u3000", ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析吉林省民政厅领导机构列表。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()

    for link in soup.select(".ldlb_20250312cs li a"):
        fields = link.select("span")
        if len(fields) < 2:
            continue
        name = _clean_name(fields[0].get_text(" ", strip=True))
        duty = _clean_text(fields[1].get_text(" ", strip=True))
        if not name or not duty or name in seen_names:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(page_rule["url"], link.get("href", ""))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(page_rule["url"]).netloc.lower()
        real_person_page = bool(re.search(r"/jgzn/ldjj/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue

        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="section=.ldlb_20250312cs; item=li a; name=span[0]; duty=span[1]",
            )
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

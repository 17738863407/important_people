from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2485',
 'domain': 'slt.fujian.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_fujian_water_leader_links_v1',
 'leader_region_selector': '.ld_con a[href]',
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
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.ld_con a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用既有 CSS/HTML 定位解析'}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省水利厅领导链接列表。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ld_con a[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[一-鿿]{2,4})\s+(?P<duty>.+)$", text)
        if not match:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        if not name or not duty or name in seen:
            continue
        if not re.search(r"厅长|党组|组长|监察官", duty):
            continue
        seen.add(name)
        href = link.get("href", "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(final_url or source_url, href)
            if candidate_url.rstrip("/") != source_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_fujian_water_leader_links_v1",
                "selector_summary": ".ld_con a；姓名 职务",
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

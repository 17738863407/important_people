from __future__ import annotations

import re
import sys
from urllib.parse import urljoin, urlparse
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2575',
 'domain': 'sthjt.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_jilin_ecology_leader_cards_v1',
 'leader_region_selector': '.e_tld_l, .e_tld_r',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body.ebg > div.m1510:nth-of-type(6) > '
                                               'div.bgfff.pos-r:nth-of-type(1) > div.w100.mt36:nth-of-type(2) > '
                                               'div.e_tld_l:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '组织机构页在线静态列出厅领导姓名和职务'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_leader_text(text: str) -> tuple[str, str] | None:
    match = re.match(r"^(?P<name>[\u4e00-\u9fff]{2,3})\s+(?P<duty>.+)$", text)
    if not match:
        return None
    duty = re.sub(r"[（(]挂职[）)]", "", _clean_text(match.group("duty")))
    return match.group("name"), duty.rstrip("，、；; ")


def _effective_href(link) -> str:
    href = link.get("href") or ""
    if href and not href.lower().startswith("javascript"):
        return href
    container = link.find_parent(class_="e_tld_l")
    if not container:
        return href
    for candidate in container.find_all("a", href=True):
        candidate_href = candidate.get("href") or ""
        if candidate_href and not candidate_href.lower().startswith("javascript"):
            return candidate_href
    return href


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    leader_links = soup.select(".e_tld_l .tabdld_r > a") + soup.select(".e_tld_r a[href]")
    for link in leader_links:
        text = _clean_text(link.get_text(" ", strip=True))
        parsed = _parse_leader_text(text)
        if not parsed:
            continue
        name, duty = parsed
        if name in seen:
            continue
        detail_url = urljoin(page_rule["url"], _effective_href(link))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(page_rule["url"]).netloc.lower()
        real_person_page = bool(re.search(r"/zzjg/tld/[a-z0-9_-]+/$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        seen.add(name)
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_jilin_ecology_leader_cards_v1",
                "selector_summary": ".e_tld_l/.e_tld_r领导链接文本",
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

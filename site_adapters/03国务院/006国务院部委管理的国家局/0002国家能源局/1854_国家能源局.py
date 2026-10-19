from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1854',
 'domain': 'www.nea.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'external_leader_pages',
 'collector': 'static_http',
 'parser': 'nea_leader_profile_pages_v1',
 'leader_region_selector': '领导活动/简历页面',
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
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '领导活动/简历页面',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    text = html_lib.unescape(text).replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _fetch_soup(url: str) -> tuple[BeautifulSoup, str]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    return BeautifulSoup(body.decode(encoding, errors="replace"), "html.parser"), final_url


def _fetch_text(url: str) -> str:
    soup, _final_url = _fetch_soup(url)
    return _clean_text(soup.get_text(" ", strip=True))


def _extract_from_text(text: str, homepage_name: str = "") -> tuple[str, str]:
    spaced_homepage_name = r"\s*".join(re.escape(char) for char in homepage_name)
    if homepage_name and re.search(rf"{spaced_homepage_name}，(?:男|女)", text):
        name = homepage_name
    else:
        name_match = re.search(r"(?:^|[\s|：])(?P<name>[\u4e00-\u9fff]{2,4})，(?:男|女)", text)
        name = re.sub(r"\s+", "", name_match.group("name")) if name_match else ""
    duty_match = re.search(r"现任(?P<duty>[^。]+)。", text)
    if not name or not duty_match:
        return "", ""
    duty = _clean_text(duty_match.group("duty"))
    return name, duty


def _leader_region_from_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one(".leadership_introduced .team") or soup.select_one(".leadership_introduced") or soup


def _extract_homepage_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """从首页领导模块动态发现领导姓名与详情链接。"""
    leader_region = _leader_region_from_html(html)
    links = []
    seen_urls: set[str] = set()
    for anchor in leader_region.select("a[href]"):
        name = _clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        leader_url = urljoin(base_url, str(anchor.get("href", "")).strip())
        if not leader_url or leader_url in seen_urls:
            continue
        seen_urls.add(leader_url)
        links.append((name, leader_url))
    return links


def _extract_homepage_title_records(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从首页领导区补充“监管总监：姓名”等无详情页的条目。"""
    from crawler_core.models import PersonRecord

    leader_region = _leader_region_from_html(html)
    text = _clean_text(leader_region.get_text("\n", strip=True))
    records = []
    for match in re.finditer(r"(?P<duty>[\u4e00-\u9fff]{2,12})：(?P<name>[\u4e00-\u9fff]{2,4})", text):
        duty = _clean_text(match.group("duty"))
        name = _clean_text(match.group("name"))
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="homepage .leadership_introduced .team colon title",
            )
        )
    return records


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析国家能源局官方领导简历页和首页领导区中的现任职务。"""
    from crawler_core.models import PersonRecord

    records = []
    seen_names: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for homepage_name, leader_url in _extract_homepage_leader_links(html, base_url):
        try:
            name, duty = _extract_from_text(_fetch_text(leader_url), homepage_name)
        except Exception:
            name, duty = "", ""
        if not name:
            name = homepage_name
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=leader_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="official leader page sentence with 现任",
            )
        )
    for row in _extract_homepage_title_records(html, final_url, page_rule):
        if row.name in seen_names:
            continue
        seen_names.add(row.name)
        records.append(row)
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

from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2623',
 'domain': 'swt.gxzf.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_guangxi_commerce_directory_detail_v2',
 'leader_region_selector': 'html > body > div.wrap.bg-white:nth-of-type(2)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap.bg-white:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导班子目录和详情页均为静态 HTML'},
             'migration': {'source': 'legacy_page_rule', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _fetch_detail_html(detail_url: str) -> str:
    request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="replace")


def _extract_duty(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"现任(?P<duty>[^。]+?)。", text)
    duty = _clean_text(match.group("duty")) if match else ""
    duty = re.sub(r"[（(]兼[）)]", "", duty).strip("，、 ")
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("html > body > div.wrap.bg-white:nth-of-type(2)") or soup
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict] = []
    seen: set[str] = set()
    for link in region.find_all("a", href=True):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        detail_url = urljoin(source_url, link.get("href") or "")
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or not (
                re.search(r"/jggk/ldbz/t\d+\.shtml(?:$|[?#])", detail_url)
                or detail_url.rstrip("/").endswith("/ldrl")
            )
            or name in seen
        ):
            continue
        try:
            duty, evidence = _extract_duty(_fetch_detail_html(detail_url))
        except Exception:
            duty, evidence = "", ""
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_guangxi_commerce_directory_detail_v2",
                "selector_summary": "领导班子姓名链接；详情现任句",
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

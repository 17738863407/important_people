from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2450',
 'domain': 'sjt.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'V004_card_person_v1',
 'leader_region_selector': '',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True, 'mode': 'person_name_link'},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
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
             'api': {'enabled': False, 'reason': '静态 HTML 入口与在线详情使用 HTML 定位解析'}}}


def _fetch_detail_html(url: str) -> str:
    """在线读取领导详情页，单页失败由调用方跳过。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析河南省审计厅领导之窗列表与人物详情。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("a[href]"):
        href = link.get("href", "").strip()
        detail_url = urldefrag(urljoin(final_url or source_url, href)).url
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == source_url.rstrip("/"):
            continue
        key_match = re.search(r"/(\d+)\.html$", detail_url)
        if not key_match:
            continue
        key = key_match.group(1)
        if key in seen:
            continue
        try:
            detail_html = _fetch_detail_html(detail_url)
        except Exception:
            continue
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        title = detail_soup.title.get_text(" ", strip=True) if detail_soup.title else ""
        name_match = re.search(r"-\s*(?P<name>[一-鿿]{2,4})$", title)
        if not name_match:
            continue
        detail_text = " ".join(detail_soup.get_text(" ", strip=True).split())
        duty_match = re.search(r"领导职务[:：]?\s*(?P<duty>[^。]+)", detail_text)
        if not duty_match:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name_match.group("name"),
                "duty": duty_match.group("duty").strip(),
                "detail_url": detail_url,
                "evidence": duty_match.group("duty").strip(),
                "parser": "custom_henan_audit_online_details_v1",
                "selector_summary": "领导之窗详情；title姓名+领导职务",
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

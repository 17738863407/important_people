from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2492',
 'domain': 'slt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hubei_water_content_cards_v1',
 'leader_region_selector': '.content .row.detail > a[href], .content .row li > a[href]:has(h2):has(p)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.content .row.detail > a[href], .content .row li > a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.content .row.detail > a[href], .content .row li > a[href]:has(h2):has(p)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.content .row.detail > a[href], .content .row li > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面使用原 CSS/HTML 定位解析'}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split()).strip()


def _split_duty_name(value: str) -> tuple[str, str]:
    text = _clean_text(value)
    for sep in ("：", ":"):
        if sep in text:
            duty, name = text.split(sep, 1)
            return _clean_text(name), _clean_text(duty)
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖北省水利厅领导信息卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_record(name: str, duty: str, detail_url: str) -> None:
        name = _clean_text(name)
        duty = _clean_text(duty)
        if not name or not duty:
            return
        key = (name, duty)
        if key in seen:
            return
        seen.add(key)
        href = str(detail_url).strip()
        candidate_url = urljoin(final_url, href)
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or urlparse(candidate_url).netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(candidate_url)[0].rstrip('/') == urldefrag(final_url)[0].rstrip('/')
        ):
            candidate_url = ""
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": candidate_url,
                "evidence": duty,
            }
        )

    top_link = soup.select_one(".content .row.detail > a[href]")
    if top_link is not None:
        h1 = top_link.select_one("h1")
        name, duty = _split_duty_name(h1.get_text(" ", strip=True) if h1 else "")
        add_record(name, duty, top_link.get("href", ""))

    for item in soup.select(".content .row li > a[href]:has(h2):has(p)"):
        name_node = item.select_one("h2")
        duty_node = item.select_one("p")
        add_record(
            name_node.get_text(" ", strip=True) if name_node else "",
            duty_node.get_text(" ", strip=True) if duty_node else "",
            item.get("href", ""),
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

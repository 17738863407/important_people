from __future__ import annotations

import re
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

PAGE_RULE = {'rule_id': '2626',
 'domain': 'swt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_hubei_commerce_leader_cards_v1',
 'leader_region_selector': '.leader li a h4',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.leader li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': '.leader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.leader li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用原 CSS/HTML 定位解析'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for card in soup.select(".leader li a[href]"):
        title = card.select_one("h4")
        if not title:
            continue
        parts = [_clean_text(part) for part in title.stripped_strings]
        parts = [part for part in parts if part]
        if len(parts) < 2:
            continue
        name = parts[0]
        duty = _clean_text("；".join(parts[1:]))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        seen.add(name)
        href = str(card.get("href") or "").strip()
        detail_url = urljoin(final_url, href) if href else ""
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or urlparse(detail_url).netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(final_url)[0].rstrip('/')
            or not urlparse(detail_url).path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_hubei_commerce_leader_cards_v1",
                "selector_summary": ".leader li a h4姓名职务",
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

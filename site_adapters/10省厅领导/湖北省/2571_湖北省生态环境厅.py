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

PAGE_RULE = {'rule_id': '2571',
 'domain': 'sthjt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_hubei_ecology_grid_leader_cards_v1',
 'leader_region_selector': 'div.grid li:has(h4 span):has(.fr b)',
 'name_selector': '.fr b',
 'duty_selector': 'h4 span',
 'detail_link_selector': 'a.xq[href], a[href*="/tld/"][href$=".shtml"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div.grid li:has(h4 span):has(.fr b)',
                     'name_selector': '.fr b',
                     'duty_selector': 'h4 span',
                     'detail_link_selector': 'a.xq[href], a[href*="/tld/"][href$=".shtml"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置，沿用在线 DOM 定位'}}}


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖北省生态环境厅领导信息页渲染后的领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in soup.select("div.grid li"):
        duty_node = item.select_one("h4 span")
        name_node = item.select_one(".fr b")
        if not duty_node or not name_node:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not name or not duty:
            continue
        link = item.select_one("a.xq[href]") or item.select_one('a[href*="/tld/"][href$=".shtml"]')
        href = str(link.get("href", "")).strip() if link else ""
        detail_url = urljoin(final_url, href) if href else ""
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or urlparse(detail_url).netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(final_url)[0].rstrip('/')
        ):
            detail_url = ""
        evidence = duty
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "source_url": str(page_rule.get("url", "")),
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=div.grid li；name=.fr b；duty=h4 span；detail=a.xq[href]；api_enabled=False",
            }
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

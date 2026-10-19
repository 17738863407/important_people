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

PAGE_RULE = {'rule_id': '2843',
 'domain': 'va.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_hubei_veterans_leader_cards_v1',
 'leader_region_selector': '.leader ul.list-b > li:has(h4):has(.leader-info)',
 'name_selector': 'h4',
 'duty_selector': '.leader-info h5 + p',
 'detail_link_selector': '.leader ul.list-b > li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.leader ul.list-b > li:has(h4):has(.leader-info)',
                     'name_selector': 'h4',
                     'duty_selector': '.leader-info h5 + p',
                     'detail_link_selector': '.leader ul.list-b > li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置，沿用在线 DOM 定位'}}}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def _field_after_label(card, label: str) -> str:
    for heading in card.select(".leader-info h5"):
        if _clean_text(heading.get_text(" ", strip=True)).replace(" ", "") == label:
            sibling = heading.find_next_sibling("p")
            return _clean_text(sibling.get_text(" ", strip=True) if sibling else "")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖北省退役军人事务厅领导信息卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for card in soup.select(".leader ul.list-b > li:has(h4):has(.leader-info)"):
        name_node = card.select_one("h4")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = _field_after_label(card, "职务")
        link = card.select_one("a.btn[href]") or card.select_one(".pic a[href]")
        href = str(link.get("href", "")).strip() if link else ""
        detail_url = urljoin(final_url, href) if href else ""
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or urlparse(detail_url).netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(final_url)[0].rstrip('/')
            or not urlparse(detail_url).path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        if not name or not duty:
            continue
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "source_url": str(page_rule.get("url", "")),
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=.leader ul.list-b > li:has(h4):has(.leader-info)；name=h4；duty=h5 职务 next p；detail=a.btn[href]；api_enabled=False",
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

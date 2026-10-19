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

PAGE_RULE = {'rule_id': '0066',
 'domain': 'agri.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hunan_agri_leader_list_v1',
 'leader_region_selector': 'div.hy-list-text li > a[href]',
 'name_selector': 'span',
 'duty_selector': 'em',
 'detail_link_selector': 'div.hy-list-text li > a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.hy-list-text li > a[href]',
                     'name_selector': 'span',
                     'duty_selector': 'em',
                     'detail_link_selector': 'div.hy-list-text li > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用原 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_evidence(value: str) -> str:
    """仅移除独立任职状态标记，保留全部具体任职语义。"""
    text = clean_text(value)
    return clean_text(re.sub(r"[<＜(（]\s*(?:挂职|兼|主持日常工作)\s*[>＞)）]", "", text))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div.hy-list-text li > a[href]；"
        "name=span；duty=em；detail=div.hy-list-text li > a[href]；api_enabled=False"
    )
    for item in soup.select("div.hy-list-text li > a[href]"):
        name_node = item.select_one("span")
        duty_node = item.select_one("em")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_evidence(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        href = str(item.get("href", "")).strip()
        base_url = final_url or str(page_rule.get("url", ""))
        detail_url = urljoin(base_url, href) if href else ""
        parsed_detail = urlparse(detail_url)
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(base_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(base_url)[0].rstrip('/')
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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

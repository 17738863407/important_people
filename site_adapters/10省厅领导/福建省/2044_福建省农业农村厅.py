from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2044',
 'domain': 'nynct.fujian.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_fujian_agri_ld_list_v1',
 'leader_region_selector': '.ld_list li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.ld_list li',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面沿用既有 CSS/HTML 定位'}}}


def _normalize_name(raw_name: str) -> str:
    return "".join(raw_name.replace("\u3164", "").replace("\u3000", "").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省农业农村厅“厅领导”侧栏列表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in soup.select(".ld_list li"):
        link = item.select_one("a[href]")
        text = " ".join(item.get_text(" ", strip=True).split())
        if not text or " " not in text:
            continue
        raw_name, duty = text.split(" ", 1)
        name = _normalize_name(raw_name)
        duty = duty.strip()
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        source_url = final_url or str(page_rule.get("url", ""))
        href = str(link.get("href") or "").strip() if link else ""
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip("/") != source_url.rstrip("/"):
                detail_url = candidate_url
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
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

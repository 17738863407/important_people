from __future__ import annotations

import re
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

PAGE_RULE = {'rule_id': '2213',
 'domain': 'rst.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'chrome_cdp',
 'parser': 'custom_gansu_rst_left_nav_cards_v1',
 'leader_region_selector': '.left.left-nav ul.jgznlist li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
             'locator': {'css': {'leader_region_selector': '.left.left-nav ul.jgznlist li',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器DOM左侧领导列表直接含姓名职务'}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    leader_region = soup.select_one(".left.left-nav") or soup
    rows: list[dict] = []
    seen_names: set[str] = set()

    for link in leader_region.select("ul.jgznlist li a[href]"):
        name_node = link.select_one("span.ldname")
        if not name_node:
            continue
        name = clean_text(name_node.get("title") or name_node.get_text(" ", strip=True)).replace(" ", "")
        if not name or not re.fullmatch(r"[\u4e00-\u9fa5]{2,6}", name):
            continue

        duty_node = name_node.find_next("span")
        duty = clean_text((duty_node.get("title") if duty_node else "") or (duty_node.get_text(" ", strip=True) if duty_node else ""))
        if not duty or name in seen_names:
            continue

        seen_names.add(name)
        detail_url = urljoin(final_url, link.get("href") or "")
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": ".left.left-nav ul.jgznlist li：span.ldname姓名 + 后续span职务",
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

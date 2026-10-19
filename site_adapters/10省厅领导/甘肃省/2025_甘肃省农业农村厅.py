from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2025',
 'domain': 'nync.gansu.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_gansu_nync_profile_cards_v1',
 'leader_region_selector': '.main li .pinfo',
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
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.main li .pinfo',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导之窗含pinfo简历现任职务'}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").replace("\u2002", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen_names = set()
    for item in soup.select(".main li .pinfo"):
        intro_node = item.select_one(".mm")
        intro = clean_text(intro_node.get_text(" ", strip=True) if intro_node else "")
        match = re.search(r"^([^，,；;。]{2,4})[，,].*?现任(.+?)。", intro)
        if not match:
            continue
        name = clean_text(match.group(1)).replace(" ", "")
        duty = clean_text(match.group(2))
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        detail_link = item.select_one('a[href*=".shtml"]')
        detail_url = urljoin(final_url, detail_link.get("href", "")) if detail_link else ""
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty.rstrip().removesuffix("。").rstrip(),
            "selector_summary": ".pinfo首个简历mm中的现任职务",
        })
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

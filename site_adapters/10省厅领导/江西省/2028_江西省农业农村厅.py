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

PAGE_RULE = {'rule_id': '2028',
 'domain': 'nync.jiangxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_jiangxi_nync_ldname_online_v1',
 'leader_region_selector': '#ldname li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '现任与历任经历混合；新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '#ldname li',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线 DOM 的 #ldname 含厅领导姓名和职务链接'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen_names = set()
    for item in soup.select("#ldname li"):
        link = item.select_one("a[href]")
        if not link:
            continue
        name = clean_text(item.get("id", "") or "").replace(" ", "")
        text = clean_text(link.get_text(" ", strip=True))
        if not name or name in seen_names or name not in text:
            continue
        duty = clean_text(text.rsplit(name, 1)[0])
        if not duty:
            continue
        href = link.get("href", "").strip()
        detail_url = "" if not href or href.startswith(("#", "javascript:")) else urljoin(final_url, href)
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
            "selector_summary": "#ldname li id姓名+链接文本职务",
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

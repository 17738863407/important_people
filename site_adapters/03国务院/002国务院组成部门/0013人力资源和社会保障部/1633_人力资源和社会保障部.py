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

PAGE_RULE = {'rule_id': '1633',
 'domain': 'www.mohrss.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_mohrss_leader_detail_title_v1',
 'leader_region_selector': '#page .leftMenuListTxt a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '#page .leftMenuListTxt a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': ['#page .leftMenu'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '入口及详情页包含反爬脚本，requests无效时必须使用Playwright；页面iframe仅为页脚',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#page .leftMenuListTxt a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '#page .leftMenuListTxt a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['#page .leftMenu'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '左侧部领导链接对应在线详情页leader_title含姓名职务'},
             'migration': {'source': 'online_detail_template',
                           'verified_status': 'online_pending',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def load_detail_title(detail_url: str) -> tuple[str, str]:
    """在线读取人物详情页的 leader_title 姓名与职务。"""
    from crawler_core.fetcher import fetch_online_html_with_fallback

    detail_result = fetch_online_html_with_fallback(detail_url)
    soup = BeautifulSoup(detail_result.html, "html.parser")
    title = soup.select_one(".leader_title")
    if not title:
        return "", ""
    parts = [clean_text(part) for part in title.get_text("\n", strip=True).splitlines()]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return "", ""
    return parts[0].replace(" ", ""), clean_text("".join(parts[1:]))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.select("#page .leftMenuListTxt a[href]"):
        raw_name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", raw_name) or raw_name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href", "")) if final_url else ""
        if not detail_url:
            continue
        name, duty = load_detail_title(detail_url)
        if not name or not duty:
            continue
        output_detail_url = detail_url
        source_url = str(page_rule.get("url", ""))
        if source_url and detail_url.rstrip("/") == source_url.rstrip("/"):
            output_detail_url = ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": output_detail_url,
                "evidence": duty,
                "selector_summary": "部领导链接+详情leader_title",
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

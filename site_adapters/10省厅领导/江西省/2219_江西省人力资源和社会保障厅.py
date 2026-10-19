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

PAGE_RULE = {'rule_id': '2219',
 'domain': 'rst.jiangxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_jx_rst_article_tag_subtitle_online_v1',
 'leader_region_selector': '.ld_list_nav li a[href*="/jxsrlzyhshbzt/col/col"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_online',
                     'detail_collector_type': 'playwright',
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
             'locator': {'css': {'leader_region_selector': '.ld_list_nav li a[href*="/jxsrlzyhshbzt/col/col"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导目录及详情 articleTag.Subtitle 提供字段'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def clean_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，])\s*", r"\1", normalized)


def extract_detail_fields(detail_html: str) -> tuple[str, str]:
    """从渲染后人物卡片读取强结构姓名和职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".leader .desc h5.title")
    duty_nodes = soup.select(".leader .desc p")
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
    duty = next(
        (
            clean_text(node.get_text(" ", strip=True))
            for node in duty_nodes
            if clean_text(node.get_text(" ", strip=True))
        ),
        "",
    )
    return name.replace(" ", ""), duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for link in soup.select(page_rule["leader_region_selector"]):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="playwright", timeout=60)
        except Exception:
            continue
        detail_name, duty_text = extract_detail_fields(detail_result.html)
        if detail_name != name or not duty_text:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty_text,
                "detail_url": detail_url,
                "evidence": duty_text,
                "selector_summary": "领导目录链接+详情articleTag.Subtitle",
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

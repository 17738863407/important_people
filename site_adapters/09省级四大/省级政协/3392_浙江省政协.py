from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3392',
 'domain': 'www.zjzx.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'raw_http',
 'parser': 'page_iframe_grouped_zhejiang_cppcc_leader_v1',
 'leader_region_selector': 'iframe[src*="szxld"] -> 在线/szxld',
 'name_selector': 'span.xm',
 'duty_selector': '前置span.zx分组标题',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'iframe[src*="szxld"] -> 在线/szxld',
                     'name_selector': 'span.xm',
                     'duty_selector': '前置span.zx分组标题',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析浙江省政协 iframe 领导分组名单。"""
    entry_soup = BeautifulSoup(html, "html.parser")
    iframe = entry_soup.select_one('iframe[src*="szxld"]')
    if iframe is None:
        return []
    iframe_url = urljoin(final_url, iframe.get("src", ""))
    response = requests.get(iframe_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    organization = page_rule["organization"]
    rows: list[dict[str, str]] = []
    current_duty = ""
    seen: set[str] = set()

    for span in soup.select("span.zx, span.xm"):
        text = re.sub(r"[\s\u00a0\u3000]+", "", span.get_text("", strip=True))
        classes = span.get("class") or []
        if "zx" in classes:
            current_duty = text
            continue
        if "xm" not in classes:
            continue
        if not current_duty or text == "数据统计" or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", text):
            continue
        if text in seen:
            continue
        seen.add(text)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": text,
                "duty": current_duty,
                "detail_url": "",
                "evidence": current_duty,
                "parser": page_rule["parser"],
                "selector_summary": "iframe /szxld span.zx+span.xm",
            }
        )
    return rows


if __name__ == "__main__":
    main()

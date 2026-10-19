from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2333',
 'domain': 'sft.jl.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': 'div#dk_main',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'div#dk_main',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面直接列出姓名、现任句与详情链接'}}}


def clean_name(text: str) -> str:
    """清理页面姓名中的空格和不换行空格。"""
    return re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip()


def clean_duty(text: str, organization: str) -> str:
    """压缩现任句排版空白，保留网页完整原句。"""
    value = re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip()
    return re.sub(r"。$", "", re.sub(r"^现任", "", value)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析吉林省司法厅厅领导列表页，避免详情页正文产生重复和噪声记录。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in soup.select("div#dk_main .c_1200_9 li"):
        name_node = item.select_one(".c_9_1 a[href]")
        duty_node = item.select_one(".c_9_1 h4")
        if not name_node or not duty_node:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_duty(duty_node.get_text(" ", strip=True), organization)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        detail_url = urljoin(final_url or source_url, name_node.get("href", ""))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(source_url).netloc.lower()
        real_person_page = bool(re.search(r"/jgsz/tld/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_jl_sft_leader_list_v1",
                "selector_summary": "div#dk_main .c_1200_9 li；name=.c_9_1 a；duty=.c_9_1 h4",
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

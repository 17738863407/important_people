from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3314',
 'domain': 'www.zg.org.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_zhigong_party_leader_v1',
 'leader_region_selector': '.nl-item',
 'name_selector': '.nl-title a',
 'duty_selector': '在线详情现任句',
 'detail_link_selector': '.nl-title a[href]',
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
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.bg',
                     'name_selector': '.nl-title a',
                     'duty_selector': '在线详情现任句',
                     'detail_link_selector': '.nl-title a[href]',
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
    """解析中国致公党中央现任领导。"""
    from bs4 import BeautifulSoup

    def clean_text(value: str) -> str:
        return re.sub(r"[\s\u00a0\u3000]+", "", value or "")

    def detail_text(detail_url: str) -> str:
        response = requests.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "html.parser")
        return re.sub(r"[\s\u00a0\u3000]+", "", detail_soup.get_text(" ", strip=True))

    def extract_duty(text: str) -> str:
        match = re.search(r"现任[^。]*。", text)
        if not match:
            return ""
        return match.group(0).removeprefix("现任").strip().removesuffix("。")

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".nl-item .nl-title a[href]"):
        name = clean_text(link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        duty = extract_duty(detail_text(detail_url))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".nl-item姓名链接 + 在线详情现任句",
            }
        )
    return rows


if __name__ == "__main__":
    main()

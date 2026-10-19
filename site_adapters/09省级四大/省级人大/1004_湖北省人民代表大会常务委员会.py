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

PAGE_RULE = {'rule_id': '1004',
 'domain': 'www.hppc.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_sidebar_hubei_people_congress_leaders_v1',
 'leader_region_selector': '.sidebar .director_list a, .director-list a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.sidebar .director_list a[href], .director-list a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '通用详情链抓取整站导航和新闻链接，改为主任之窗侧栏解析；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.sidebar .director_list a, .director-list a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.sidebar .director_list a[href], .director-list a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩人大页面中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析湖北省人大常委会“主任之窗”侧栏成员入口。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    selector_summary = "strategy=custom_parse_page；selector=.director_list a dt/dd；exclude=news_links"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".director_list a[href], .director-list a[href]"):
        duty_node = link.select_one("dt")
        name_node = link.select_one("dd")
        duty = clean_name(duty_node.get_text(" ", strip=True)) if duty_node else ""
        name = clean_name(name_node.get_text(" ", strip=True)) if name_node else clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(page_url, str(link.get("href", "")))
        evidence = duty
        if not duty:
            response = requests.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_text = " ".join(BeautifulSoup(response.text, "html.parser").stripped_strings)
            sentence = re.search(r"现任[^。]*。", detail_text)
            if sentence:
                evidence = sentence.group(0)
                duty_match = re.search(r"人大常委会([^、，。]*)", evidence)
                duty = clean_name(duty_match.group(1)) if duty_match else "现任职务"
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
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

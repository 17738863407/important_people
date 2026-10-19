from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3399',
 'domain': 'zrzy.jiangsu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_jiangsu_natural_resources_leader_v1',
 'leader_region_selector': '领导名单 a[href*="/ldcy/"]',
 'name_selector': '领导链接文本',
 'duty_selector': '详情姓名后简介及分工前',
 'detail_link_selector': 'a[href*="/ldcy/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_online',
                     'detail_collector_type': 'chrome_cdp',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '领导名单 a[href*="/ldcy/"]',
                     'name_selector': '领导链接文本',
                     'duty_selector': '详情姓名后简介及分工前',
                     'detail_link_selector': 'a[href*="/ldcy/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _parse_detail_duty(detail_html: str, name: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one("span.style4")
    duty_node = soup.select_one("span.style2")
    found_name = re.sub(r"[\s\u00a0\u3000]+", "", name_node.get_text("", strip=True) if name_node else "")
    if found_name != name or not duty_node:
        return ""
    duty = duty_node.get_text(" ", strip=True)
    duty = re.sub(r"\s+", "", duty).rstrip("，,；;。")
    duty = duty.replace("副厅长省", "副厅长，省")
    duty = duty.replace("党组成员省纪委", "党组成员，省纪委")
    duty = duty.replace("组长二级", "组长，二级")
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析江苏省自然资源厅领导名单和详情页。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/ldcy/"]'):
        name = re.sub(r"[\s\u00a0\u3000]+", "", link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome_cdp", timeout=45)
        except Exception:
            continue
        duty = _parse_detail_duty(detail_result.html, name)
        if not duty or re.search(r"(负责|主持|分管|工作|简介)", duty):
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
                "selector_summary": "领导链接+详情标题职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()

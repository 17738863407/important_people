from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_duty(value: str) -> str:
    """清理方括号包裹的职务文本。"""
    text = clean_text(value)
    return text.strip("[]［］").removeprefix("现")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析海南省公安厅领导卡片列表。"""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".gkpd-l-nr .gkpd-ldd li a[href]"):
        name = clean_text(link.select_one("em").get_text(" ", strip=True) if link.select_one("em") else "")
        duty = clean_duty(link.select_one("span").get_text(" ", strip=True) if link.select_one("span") else "")
        duty = re.sub(rf"^{re.escape(name)}[，,]\s*现任\s*", "", duty)
        duty = re.sub(r"^现任\s*", "", duty)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(base_url, str(link.get("href", "")))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "hainan_police_leader_card_v1",
            }
        )

    return rows


PAGE_RULE = {'rule_id': '0600',
 'domain': 'ga.hainan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'hainan_police_leader_card_v1',
 'leader_region_selector': '.gkpd-l-nr .gkpd-ldd li',
 'name_selector': 'li a[href] > em',
 'duty_selector': 'li a[href] > span',
 'detail_link_selector': 'li a[href]',
 'content_scope': {'start_anchor': '省公安厅领导', 'end_anchor': '机构职能', 'include_selectors': ['.gkpd-l-nr .gkpd-ldd'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'li a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.gkpd-l-nr .gkpd-ldd li',
                     'name_selector': 'li a[href] > em',
                     'duty_selector': 'li a[href] > span',
                     'detail_link_selector': 'li a[href]',
                     'content_scope': {'start_anchor': '省公安厅领导',
                                       'end_anchor': '机构职能',
                                       'include_selectors': ['.gkpd-l-nr .gkpd-ldd'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': True}}}


def main() -> None:
    """运行当前页面级爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

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

PAGE_RULE = {'rule_id': '1549',
 'domain': 'www.mee.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_mee_cjcs_zzjg_ganbu_cards_v1',
 'leader_region_selector': 'ul.cjcs_zzjg_ganbu',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'ul.cjcs_zzjg_ganbu > a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.cjcs_zzjg_ganbu',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'ul.cjcs_zzjg_ganbu > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'online_page_rule', 'verified_status': 'online_pending', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows = []
    seen = set()
    for link in soup.select("ul.cjcs_zzjg_ganbu > a[href]"):
        item = link.select_one("li")
        name_node = item.select_one("strong") if item else None
        if not item or not name_node:
            continue
        raw_name = clean_text(name_node.get_text(" ", strip=True))
        name = raw_name.replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        duty_node = item.select_one("span")
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty or not re.search(r"书记|部长|成员|组长|局长", duty):
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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

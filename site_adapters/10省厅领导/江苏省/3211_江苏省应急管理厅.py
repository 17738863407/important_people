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

PAGE_RULE = {'rule_id': '3211',
 'domain': 'yjglt.jiangsu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_jiangsu_emergency_leader_v1',
 'leader_region_selector': '.ldlb-txt a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_online',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#barrierfree_container > div.wrap.w1100:nth-of-type(3) > '
                                               'div.main-content.cf:nth-of-type(2) > '
                                               'div.main-content-right.fdzdgknr-content:nth-of-type(2) > div.fding1 > '
                                               'ul.inner > div > div > div.ld-more:nth-of-type(4)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
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


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\xa0", ""))


def detail_duty(detail_html: str, name: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    parts = [re.sub(r"\s+", " ", item).strip() for item in soup.get_text("\n", strip=True).splitlines()]
    parts = [item for item in parts if item]
    target = clean_name(name)
    for index, item in enumerate(parts):
        if clean_name(item) == target and index + 1 < len(parts):
            duty = parts[index + 1].strip()
            if duty and not duty.startswith(".") and "function" not in duty:
                return duty, f"{item}；{duty}"
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析江苏省应急管理厅领导列表及人物详情页。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".ldlb-txt a[href]"):
        name = clean_name(link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="requests", timeout=20)
        except Exception:
            continue
        duty_core, _ = detail_duty(detail_result.html, name)
        if not duty_core:
            continue
        seen.add(name)
        duty = duty_core
        if duty.startswith("省应急管理厅"):
            duty = duty.replace("省应急管理厅", organization, 1)
        elif not duty.startswith(organization) and not duty.startswith("国家矿山安全监察局") and not duty.startswith("省消防救援总队") and not duty.startswith("省水利厅"):
            duty = f"{organization}{duty}"
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": "" if detail_url.rstrip("/") == page_rule["url"].rstrip("/") else detail_url,
                "evidence": duty_core,
                "parser": page_rule["parser"],
                "selector_summary": ".ldlb-txt a + 在线详情页姓名后相邻职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()

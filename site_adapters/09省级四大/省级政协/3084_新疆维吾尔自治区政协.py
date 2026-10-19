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

PAGE_RULE = {'rule_id': '3084',
 'domain': 'www.xjzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': 'xinjiang_cppcc_grouped_leader_cards_v2',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinjiang_cppcc_grouped_cards_v2',
 'leader_region_selector': '.lingdao_ind01',
 'name_selector': ':scope > .main/.vice/.secretary .text a[href]',
 'duty_selector': ':scope > .main/.vice/.secretary > .title span',
 'detail_link_selector': '.text a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '现行入口直接按主席、副主席、秘书长分组展示人物卡片；只解析lingdao_ind01的三个直属分组，排除全站导航。',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.list:nth-of-type(5)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def valid_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fa5·]{2,20}", value))


def add_row(
    rows: list[dict[str, str]],
    seen: set[str],
    page_rule: dict,
    name: str,
    duty: str,
    href: str,
    evidence: str,
) -> None:
    name = normalize_name(name)
    duty = re.sub(r"\s+", "", clean_text(duty)).removeprefix("现任").strip().removesuffix("。")
    href = href.replace("/2026/01/300/", "/2026/01/30/")
    if not valid_name(name) or not duty or name in seen:
        return
    seen.add(name)
    rows.append(
        {
            "organization": page_rule["organization"],
            "url": page_rule["url"],
            "name": name,
            "duty": duty,
            "detail_url": urljoin(page_rule["url"], href),
            "evidence": clean_text(evidence).removeprefix("现任").strip().removesuffix("。"),
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": ".lingdao_ind01直属主席、副主席、秘书长分组；.text a人物卡片及独立详情链接",
        }
    )


def fetch_detail(detail_url: str) -> str:
    """在线读取政协领导详情页。"""
    response = requests.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现行入口的主席、副主席、秘书长卡片分组解析。"""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    entry_soup = BeautifulSoup(html, "html.parser")
    region = entry_soup.select_one(".lingdao_ind01")
    if region is None:
        raise RuntimeError("政协领导入口缺少领导卡片区域")
    for group in region.select(":scope > .main, :scope > .vice, :scope > .secretary"):
        title_node = group.select_one(":scope > .title span")
        group_title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        if group_title not in {"主席", "副主席", "秘书长"}:
            continue
        for link in group.select(".text a[href]"):
            add_row(
                rows,
                seen,
                page_rule,
                link.get_text(" ", strip=True),
                group_title,
                urljoin(final_url, str(link.get("href") or "")),
                group_title,
            )
    if not rows:
        raise RuntimeError("政协领导卡片未解析到人物记录")
    return rows


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
import re

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2456',
 'domain': 'sjt.nx.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V009_text_profile_paragraph_v1',
 'leader_region_selector': 'html > body > section.main',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > section.main',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    text = text.replace("\u200d", "").replace("\ufeff", "")
    return "".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _fetch_online_html(url: str) -> str:
    """以官网可接受的简洁请求头在线重取领导页面。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析宁夏回族自治区审计厅领导成员合并正文。"""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select(".TRS_UEDITOR p"):
        soup = BeautifulSoup(_fetch_online_html(page_rule["url"]), "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    texts = [_clean_text(node.get_text(" ", strip=True)) for node in soup.select(".TRS_UEDITOR p")]
    names: set[str] = set()
    for text in texts:
        match = re.match(r"^(?P<name>[一-鿿]{2,3})[:：]", text)
        if match:
            names.add(match.group("name"))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for text in texts:
        if "领导成员" in text or not text.startswith("自治区审计厅"):
            continue
        for name in sorted(names, key=len, reverse=True):
            if not text.endswith(name) or name in seen:
                continue
            duty = text[: -len(name)].strip()
            if not duty:
                continue
            seen.add(name)
            rows.append(
                {
                    "organization": organization,
                    "url": source_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": "custom_ningxia_audit_merged_profile_v1",
                    "selector_summary": ".TRS_UEDITOR p；职务姓名标题",
                }
            )
            break

    for text in texts:
        bio_match = re.match(
            r"^(?P<name>[一-鿿]{2,3})[:：].*?(?P<evidence>现任自治区审计厅(?P<duty>[^。]*)。)",
            text,
        )
        if not bio_match:
            continue
        name = bio_match.group("name")
        if name in seen:
            continue
        duty = bio_match.group("evidence").removeprefix("现任").strip("。")
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_ningxia_audit_merged_profile_v1",
                "selector_summary": ".TRS_UEDITOR p；现任职务句补充",
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

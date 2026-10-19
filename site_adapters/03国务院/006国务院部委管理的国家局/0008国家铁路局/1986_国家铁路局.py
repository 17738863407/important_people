from __future__ import annotations

import html as html_lib
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

PAGE_RULE = {'rule_id': '1986',
 'domain': 'www.nra.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'chrome_cdp',
 'extract_mode': 'custom',
 'collector': 'chrome_cdp',
 'parser': 'online_national_railway_administration_org_leaders_v1',
 'leader_region_selector': '组织机构领导正文',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '组织机构领导正文',
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
                           'behavior_changed': True}}}


def _clean_text(text: str) -> str:
    text = html_lib.unescape(text).replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _html_to_text(html: str) -> str:
    text = re.sub(r"<!--[\s\S]*?-->", " ", html)
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return _clean_text(text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析国家铁路局组织机构页领导名单。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for link in soup.select(".jigou_main a[href]"):
        name_node = link.select_one("p b")
        paragraph = link.select_one("p")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(paragraph.get_text(" ", strip=True).replace(name, "", 1)) if paragraph else ""
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=urljoin(final_url, link.get("href", "")),
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="organization .jigou_main a中p b姓名+p职务",
            )
        )
    for link in soup.select(".jigou_main2 a[href]"):
        text_node = link.select_one("b.mobileNone")
        parts = list(text_node.stripped_strings) if text_node else []
        name = _clean_text(parts[0]) if parts else ""
        duty = _clean_text(" ".join(parts[1:])) if len(parts) > 1 else ""
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=urljoin(final_url, link.get("href", "")),
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="organization .jigou_main2 b.mobileNone姓名职务",
            )
        )
    return records


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

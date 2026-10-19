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

PAGE_RULE = {'rule_id': '2065',
 'domain': 'www.pbc.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'pbc_bank_leaders_v1',
 'leader_region_selector': '',
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
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
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


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return _clean_text(text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析中国人民银行行领导列表。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for table in soup.select("table[height='268']"):
        rows = table.select("tr")
        if len(rows) < 3:
            continue
        duty = _clean_text(rows[-2].get_text(" ", strip=True))
        name_link = rows[-1].select_one("a[href]")
        name = _clean_text(name_link.get_text(" ", strip=True)).replace(" ", "") if name_link else ""
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=urljoin(final_url, name_link.get("href", "")),
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="行领导table[height=268]倒数第二行职务+末行姓名链接",
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

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

PAGE_RULE = {'rule_id': '2024',
 'domain': 'nync.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'raw_http',
 'parser': 'anhui_agriculture_info_list_entries_v1',
 'leader_region_selector': '#xxgk_lmcon .xxgk_nav_list li',
 'name_selector': 'a.title[href]标题中机构名前文本',
 'duty_selector': 'a.title[href]标题中机构名起始的完整职务文本',
 'detail_link_selector': 'a.title[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': ['#xxgk_lmcon'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '入口查询参数包含catId，必须保留原始HTTP响应；人物仅限#xxgk_lmcon机构领导列表',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#xxgk_lmcon .xxgk_nav_list li',
                     'name_selector': 'a.title[href]标题中机构名前文本',
                     'duty_selector': 'a.title[href]标题中机构名起始的完整职务文本',
                     'detail_link_selector': 'a.title[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['#xxgk_lmcon'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用既有文本行定位解析'}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _html_to_lines(html: str) -> list[str]:
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "\n", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", "", html)
    return [line for line in (_clean_text(item) for item in text.splitlines()) if line]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析机构领导公开列表中的姓名和完整职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    for link in soup.select("#xxgk_lmcon .xxgk_nav_list li a.title[href]"):
        compact_line = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        split_index = compact_line.find(organization)
        if split_index <= 0:
            continue
        name = compact_line[:split_index]
        duty = compact_line[split_index:]
        if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", name):
            continue
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(page_url, href) if href and not href.lower().startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == page_url.rstrip("/"):
            detail_url = ""
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "leader=#xxgk_lmcon .xxgk_nav_list li；title=a.title[href]；split=机构名边界",
            }
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

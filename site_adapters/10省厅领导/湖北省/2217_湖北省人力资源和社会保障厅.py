from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2217',
 'domain': 'rst.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'hubei_hrss_h4_cards_v1',
 'leader_region_selector': '.leader ul li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
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
             'api': {'enabled': False, 'reason': '领导信息卡片已直接包含姓名、职务和详情链接'}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析湖北省人社厅领导信息卡片。"""
    records: list[object] = []
    seen: set[str] = set()
    for li_html in re.findall(r"(?is)<li\b[^>]*>.*?</li>", html):
        h4_values = [_clean_text(item) for item in re.findall(r"(?is)<h4[^>]*>(.*?)</h4>", li_html)]
        href_match = re.search(r'(?is)<a\b[^>]*href="([^"]+)"', li_html)
        if len(h4_values) < 2:
            continue
        name, duty = h4_values[0], h4_values[1]
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = ""
        if href_match:
            href = html_lib.unescape(href_match.group(1)).strip()
            candidate_url = urljoin(final_url, href)
            parsed_candidate = urlparse(candidate_url)
            if (
                not href.startswith(('#', 'javascript:'))
                and parsed_candidate.netloc.lower() == urlparse(final_url).netloc.lower()
                and parsed_candidate.path.lower().endswith(('.shtml', '.html', '.htm'))
            ):
                detail_url = candidate_url
        records.append(_make_record(page_rule, name, duty, detail_url))
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

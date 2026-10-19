from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2330',
 'domain': 'sft.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_hubei_sft_card_h4_v1',
 'leader_region_selector': '.list-p li a h4',
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
 'locator': {'css': {'leader_region_selector': '.list-p li a h4',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导卡片 h4 以换行分隔姓名和职务'}}}


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


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析湖北省司法厅领导信息卡片。"""
    rows: list[object] = []
    seen: set[str] = set()
    pattern = re.compile(r'<li class="[^"]*"[^>]*>\s*<a href="(?P<href>[^"]+)"[^>]*>.*?<h4[^>]*>(?P<name>.*?)<br\s*/?>(?P<duty>.*?)</h4>', re.S)
    for match in pattern.finditer(html):
        name = _clean_text(match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        href = unescape(match.group("href")).strip()
        detail_url = urljoin(final_url, href)
        parsed_detail = urlparse(detail_url)
        if (
            href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        rows.append(_make_record(page_rule, name, duty, detail_url))
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

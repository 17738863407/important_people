from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2212',
 'domain': 'rst.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'fujian_hrss_leader_cards_v1',
 'leader_region_selector': '.ld_div li',
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
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.w_1300_2021:nth-of-type(4) > div.pad-bot2 > '
                                               'div.ejym-con > div.ejove:nth-of-type(2) > '
                                               'div.ld_div.pad_t35:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线厅领导卡片列表已包含姓名、职务和详情链接'}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> dict[str, str]:
    duty = duty.strip(" ，,、；;")
    return {
        "name": name,
        "duty": duty,
        "detail_url": detail_url,
        "evidence": duty,
        "confidence": "high",
        "parser": str(page_rule.get("parser", "")),
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省人社厅厅领导卡片列表。"""
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = final_url or str(page_rule.get("url", ""))
    for li_html in re.findall(r"(?is)<li\b[^>]*>.*?</li>", html):
        name_match = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", li_html)
        duty_match = re.search(r"(?is)<em[^>]*>(.*?)</em>", li_html)
        href_match = re.search(r'(?is)<a\b[^>]*href="([^"]+)"', li_html)
        if not name_match or not duty_match:
            continue
        name = _clean_text(name_match.group(1))
        duty = _clean_text(duty_match.group(1))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = ""
        if href_match:
            href = href_match.group(1).strip()
            if href and not href.lower().startswith(("#", "javascript:")):
                candidate_url = urljoin(source_url, href)
                if candidate_url.rstrip("/") != str(page_rule.get("url", "")).rstrip("/"):
                    detail_url = candidate_url
        records.append(_make_record(page_rule, name, duty, detail_url))
    return records


def fetch_current_leader_page(page_rule: dict) -> object:
    """旧个人页失效时，从同站厅领导入口跟随当前人物页跳转。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url", ""))
    try:
        return fetch_html_with_strategy(entry_url, "raw_http")
    except Exception as entry_error:
        listing_url = urljoin(entry_url, "../")
        listing_result = fetch_html_with_strategy(listing_url, "raw_http")
        refresh_match = re.search(
            r'(?is)<meta\b[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\'][^"\']*url=([^"\'>]+)',
            listing_result.html,
        )
        if refresh_match is None:
            raise RuntimeError(f"旧入口失效且厅领导入口无当前页跳转：{entry_error}")
        candidate = urljoin(listing_result.final_url, refresh_match.group(1).strip())
        listing_parts = urlsplit(listing_result.final_url)
        candidate_parts = urlsplit(candidate)
        if candidate_parts.netloc.lower() != listing_parts.netloc.lower():
            raise RuntimeError("厅领导入口跳转到站外地址")
        if not candidate_parts.path.startswith(listing_parts.path.rstrip("/") + "/"):
            raise RuntimeError("厅领导入口跳转超出当前栏目")
        return fetch_html_with_strategy(
            candidate,
            "raw_http",
            referer=listing_result.final_url,
        )


def main() -> None:
    """运行当前页面级在线爬虫，并保留规则主表业务字段。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        apply_business_location,
        make_failure_record,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    page_rule = apply_business_source(PAGE_RULE)
    try:
        page_result = fetch_current_leader_page(page_rule)
        rows = normalize_inline_rows(
            page_rule,
            parse_page(page_result.html, page_result.final_url, page_rule),
        )
        if not rows:
            raise RuntimeError("当前厅领导卡片解析结果为空")
    except Exception as error:
        rows = [make_failure_record(page_rule, str(error))]

    normalize_record_source_urls(page_rule, rows)
    apply_business_location(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        if not row.script_sequence:
            row.script_sequence = normalize_script_sequence(page_rule.get("rule_id"))
    output_path = project_dir / "outputs" / build_output_name(
        str(page_rule.get("rule_id", "")),
        str(page_rule.get("organization", "机构")),
    )
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

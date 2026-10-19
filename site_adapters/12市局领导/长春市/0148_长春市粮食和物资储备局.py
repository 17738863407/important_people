from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0148",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_grain_leader_list_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changchun_grain_leader_list_detail_v1",
    "leader_region_selector": "ul.x_zcjd_li.mar0 > li",
    "name_selector": "a[target='_blank'][href]",
    "duty_selector": "div.TRS_Editor中的完整现任句",
    "detail_link_selector": "a[target='_blank'][href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.x_zcjd_li.mar0"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "a[target='_blank'][href]",
        "detail_parser": "same_name_current_sentence_v1",
        "detail_name_selector": "div.TRS_Editor首句",
        "detail_duty_selector": "div.TRS_Editor中的完整现任句",
        "detail_content_selector": "div.TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": (
        "列表页含无关iframe；站点模板中的浏览器版本提示会触发online有效性误判；"
        "职务必须由同名人物详情页当前句在线取得"
    ),
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_verified_detail",
    "locator": {
        "css": {
            "leader_region_selector": "ul.x_zcjd_li.mar0 > li",
            "name_selector": "a[target='_blank'][href]",
            "detail_content_selector": "div.TRS_Editor",
        },
        "api": {
            "enabled": False,
            "reason": "列表页和人物详情页均为稳定静态HTML",
        },
        "migration": {
            "source": "legacy_inline_list_detail_parser",
            "verified_status": "verified_current_online_detail",
            "behavior_changed": True,
        },
    },
}


CURRENT_DUTY_PATTERN = re.compile(r"现任[^。]*。")
DETAIL_PATH_PATTERN = re.compile(r"/xxfb/ldxx/\d{6}/t\d{8}_\d+\.html$")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版产生的字间空格。"""
    return clean_text(text).replace(" ", "")


def clean_duty_evidence(text: str) -> str:
    """删除固定引导词、纯句末句号及明确尾随的全面工作职责。"""
    value = re.sub(r"^现任\s*", "", clean_text(text))
    value = re.sub(r"[，,]\s*(?:负责|主持)全面工作\s*[。．]?\s*$", "", value)
    value = re.sub(r"[。．]\s*$", "", value)
    return clean_text(value)


def extract_detail_evidence(detail_html: str, expected_name: str) -> str:
    """核对详情正文姓名，并返回同一正文中的完整现任原句。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    content = detail_soup.select_one("div.TRS_Editor")
    if content is None:
        return ""
    content_text = clean_text(content.get_text(" ", strip=True))
    compact_text = content_text.replace(" ", "")
    if not compact_text.startswith(f"{expected_name}，"):
        return ""
    match = CURRENT_DUTY_PATTERN.search(content_text)
    return clean_duty_evidence(match.group(0)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持目录顺序，在线核对每个同域人物详情页的姓名和现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one("a[target='_blank'][href]")
        if link is None:
            continue
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, clean_text(link.get("href", "")))
        parsed_url = urlsplit(detail_url)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name)
            or parsed_url.netloc.lower() != source_host
            or DETAIL_PATH_PATTERN.fullmatch(parsed_url.path) is None
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        evidence = extract_detail_evidence(detail_result.html, name)
        if not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_list_to_detail；leader=ul.x_zcjd_li.mar0 > li；"
                    "name=list_link；detail=same_host_ldxx_link；"
                    "duty=verified_same_name_detail_current_sentence"
                ),
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

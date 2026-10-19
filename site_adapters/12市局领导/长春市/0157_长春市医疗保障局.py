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
    "rule_id": "0157",
    "page_type": "人物目录详情页",
    "structure_group": "changchun_medical_security_detail_prefix_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changchun_medical_security_detail_prefix_v1",
    "leader_region_selector": "ul.news_list_ul > li",
    "name_selector": "a[href]",
    "duty_selector": "同名详情div.TRS_Editor中姓名前的标题职务",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.news_list_ul"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "a[href]",
        "detail_parser": "verified_detail_prefix_duty_v1",
        "detail_name_selector": "div.TRS_Editor标题中的列表姓名",
        "detail_duty_selector": "div.TRS_Editor标题中姓名前文本",
        "detail_content_selector": "div.TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": "人物详情标题分别使用font、p或外层div，需依靠同名正文前缀统一核验",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_prefix",
    "locator": {
        "css": {
            "leader_region_selector": "ul.news_list_ul > li",
            "name_selector": "a[href]",
            "detail_content_selector": "div.TRS_Editor",
        },
        "api": {
            "enabled": False,
            "reason": "列表和详情均为静态HTML，详情正文标题直接包含职务与姓名",
        },
        "migration": {
            "source": "legacy_inline_list_detail_parser",
            "verified_status": "verified_current_online_detail",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|纪检|组长")
DETAIL_PATH_PATTERN = re.compile(r"/jgsz/ldbz/\d{6}/t\d{8}_\d+\.html$")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版产生的字间空格。"""
    return clean_text(text).replace(" ", "")


def extract_detail_evidence(detail_html: str, expected_name: str) -> str:
    """核对详情正文标题，并读取列表姓名之前的原始职务字段。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    content = detail_soup.select_one("div.TRS_Editor")
    if content is None:
        return ""
    content_text = clean_text(content.get_text(" ", strip=True))
    if expected_name not in content_text:
        return ""
    evidence = clean_text(content_text.split(expected_name, 1)[0])
    if not evidence or len(evidence) > 60 or DUTY_HINT_PATTERN.search(evidence) is None:
        return ""
    return evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持目录顺序，在线核对各详情正文标题中的姓名和原始职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one("a[href]")
        if link is None:
            continue
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, clean_text(link.get("href", "")))
        parsed_url = urlsplit(detail_url)
        if (
            NAME_PATTERN.fullmatch(name) is None
            or parsed_url.netloc.lower() != source_host
            or DETAIL_PATH_PATTERN.fullmatch(parsed_url.path) is None
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, strategy="requests")
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
                    "strategy=custom_list_to_detail；leader=ul.news_list_ul > li；"
                    "name=list_link；detail=same_host_ldbz_link；"
                    "duty=verified_detail_editor_prefix_before_name"
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

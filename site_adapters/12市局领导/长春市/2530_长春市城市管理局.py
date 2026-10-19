from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2530",
    "page_type": "人物目录详情页",
    "structure_group": "changchun_city_management_list_online_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_detail",
    "collector": "static_http",
    "parser": "page_inline_changchun_city_management_list_online_current_sentence_v1",
    "leader_region_selector": ".listpage .con ul > li > a[href]",
    "name_selector": "纯中文姓名链接文本",
    "duty_selector": "详情正文当前人物区域内完整现任句",
    "detail_link_selector": ".listpage .con ul > li > a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".listpage .con ul"],
        "exclude_selectors": ["领导班子和其他公告", ".date", "header", "footer"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "online_current_sentence_from_dynamic_person_links",
        "detail_collector_type": "requests",
        "detail_link_selector": ".listpage .con ul > li > a[href]",
        "detail_parser": "current_sentence_in_detail_editor",
        "detail_name_selector": "list_anchor_text",
        "detail_duty_selector": "现任句",
        "detail_content_selector": ".TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": "人物列表混有领导班子公告，详情正文含分工、审核人和履历；只接受纯姓名链接并取对应详情完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_person_links_online_detail_current_sentence",
    "locator": {
        "css": {
            "leader_region_selector": ".listpage .con ul > li > a[href]",
            "name_selector": "fullmatch_chinese_name",
            "detail_link_selector": "same_anchor_href",
            "detail_content_selector": ".TRS_Editor",
        },
        "api": {
            "enabled": False,
            "reason": "静态列表和独立详情正文可在线稳定复现",
        },
        "migration": {
            "source": "legacy_local_detail_input_and_broken_undefined_html",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,4}")
CURRENT_SENTENCE_PATTERN = re.compile(r"现\s*任\s*(?P<sentence>[^。]+?)\s*。")


def clean_text(text: str) -> str:
    """压缩HTML排版空白，不改变网页文字语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def compact_text(text: str) -> str:
    """移除详情正文因排版产生的词内空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", text or "").strip()


def fetch_current_sentence(detail_url: str) -> str:
    """在线抓取详情页并返回当前人物区域中的完整现任句。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    fetched = fetch_html_with_strategy(detail_url, strategy="requests")
    soup = BeautifulSoup(fetched.html, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        return ""
    text = clean_text(region.get_text(" ", strip=True))
    match = CURRENT_SENTENCE_PATTERN.search(text)
    if match is None:
        return ""
    return compact_text(match.group("sentence"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按列表顺序在线读取每个人物详情页的完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.select(page_rule["leader_region_selector"]):
        name = compact_text(anchor.get_text(" ", strip=True))
        if NAME_PATTERN.fullmatch(name) is None or name in seen:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        evidence = fetch_current_sentence(detail_url)
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=pure_name_list_links；detail=online_TRS_Editor；duty=complete_current_sentence；announcement_and_responsibility=excluded",
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

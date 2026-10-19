from __future__ import annotations

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


PAGE_RULE = {
    "rule_id": "1099",
    "page_type": "多人物详情合并页",
    "structure_group": "iterchina_current_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_iterchina_current_leader_cards_v2",
    "leader_region_selector": ".neiye-list.xrld li",
    "name_selector": ".title",
    "duty_selector": ".des",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".neiye-list.xrld"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_link_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 10,
    },
    "risk_flag": "简介同时含履历；仅在每个人物卡片的des字段内提取完整现任句，不扫描整页",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_current_sentence_cards",
    "locator": {
        "css": {
            "leader_region_selector": ".neiye-list.xrld li",
            "name_selector": ".title",
            "duty_selector": ".des",
            "detail_link_selector": "a[href]",
        },
        "api": {"enabled": False, "reason": "当前静态HTML人物卡片直接提供姓名、简介和详情链接"},
        "migration": {
            "source": "legacy_business_source_and_semantic_duty_stripping_removed",
            "verified_status": "verified_current_raw_http",
            "behavior_changed": True,
        },
    },
}


def compact(value: str) -> str:
    """清理HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片顺序提取姓名、完整现任句和真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(page_rule["leader_region_selector"]):
        name_node = item.select_one(page_rule["name_selector"])
        desc_node = item.select_one(page_rule["duty_selector"])
        if name_node is None or desc_node is None:
            continue
        name = compact(name_node.get_text(" ", strip=True))
        description = compact(desc_node.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", description)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or current_match is None:
            continue
        current_sentence = current_match.group(0)
        evidence = current_sentence.removeprefix("现任").removesuffix("。").strip()
        link_node = item.select_one(page_rule["detail_link_selector"])
        href = str(link_node.get("href") or "").strip() if link_node is not None else ""
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=current_person_card；evidence=current_sentence；order=card_dom",
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

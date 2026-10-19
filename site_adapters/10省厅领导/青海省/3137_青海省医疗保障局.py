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


def clean_text(value: str) -> str:
    """清理字段排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """通过相邻且同链接的姓名段、职务段提取局领导。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name_link in soup.select(".xpage-container p > a[href]"):
        name = re.sub(r"\s+", "", name_link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        name_paragraph = name_link.parent
        duty_paragraph = name_paragraph.find_next_sibling("p")
        duty_link = duty_paragraph.select_one("a[href]") if duty_paragraph else None
        if duty_link is None or duty_link.get("href") != name_link.get("href"):
            continue
        duty = clean_text(duty_link.get_text(" ", strip=True))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(name_link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_medical_security_cards_v2",
                "selector_summary": "scope=.xpage-container；name=p>a；duty=相邻p>a且href相同；detail=href",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3137",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_medical_security_linked_fields",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_medical_security_cards_v2",
    "leader_region_selector": ".xpage-container p > a[href]",
    "name_selector": "姓名p>a",
    "duty_selector": "相邻同href职务p>a",
    "detail_link_selector": "姓名p>a[href]",
    "content_scope": {
        "start_anchor": "局领导",
        "end_anchor": "",
        "include_selectors": [".xpage-container"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "姓名p>a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xpage-container p > a[href]",
            "name_selector": "姓名p>a",
            "duty_selector": "相邻同href职务p>a",
            "detail_link_selector": "姓名p>a[href]",
            "content_scope": {
                "start_anchor": "局领导",
                "end_anchor": "",
                "include_selectors": [".xpage-container"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML以相邻同链接段落直出姓名和职务"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

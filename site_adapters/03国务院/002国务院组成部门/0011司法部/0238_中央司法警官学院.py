from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0238",
    "page_type": "人物列表完整页",
    "structure_group": "cicp_leader_text_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_cicp_leader_text_list_v2",
    "leader_region_selector": ".news-list .news-item-title",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导班子",
        "end_anchor": "共6条记录",
        "include_selectors": [".news-list"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "站点HTTPS仅浏览器可稳定握手；列表文本以党委职务为稳定分界，页面无人物独立详情链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_leader_text_list",
    "locator": {
        "css": {"leader_region_selector": ".news-list .news-item-title"},
        "api": {"enabled": False, "reason": "当前浏览器渲染DOM领导班子列表直接提供姓名和职务"},
        "migration": {
            "source": "legacy_offline_dependency_and_business_source_removed",
            "verified_status": "verified_current_online_playwright",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip(" »")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导班子列表DOM顺序，以党委职务为边界拆分姓名和职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for item in soup.select(".news-list .news-item-title"):
        text = _clean_text(item.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+(党委.+)", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = _clean_text(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".news-list .news-item-title姓名党委职务文本",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

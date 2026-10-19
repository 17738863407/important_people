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
    "rule_id": "2505",
    "page_type": "人物列表完整页",
    "structure_group": "slwr_leader_text_links_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_slwr_leader_text_links_v2",
    "leader_region_selector": ".leaderships a[href]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": ".leaderships a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".leaderships"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_link_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".leaderships a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 10,
    },
    "risk_flag": "同一卡片含空文本图片链接和姓名职务文本链接；仅解析能完整拆分姓名与职务的文本链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_leader_text_links",
    "locator": {
        "css": {"leader_region_selector": ".leaderships a[href]", "detail_link_selector": ".leaderships a[href]"},
        "api": {"enabled": False, "reason": "当前静态HTML领导区域文本链接直接提供姓名、职务和详情链接"},
        "migration": {
            "source": "legacy_duty_keyword_filter_and_business_source_removed",
            "verified_status": "verified_current_raw_http",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导区域文本链接的DOM顺序拆分姓名与原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for link in soup.select(".leaderships a[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,20})\s+(.+)", text)
        if match is None:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen_names:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".leaderships姓名职务文本链接",
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

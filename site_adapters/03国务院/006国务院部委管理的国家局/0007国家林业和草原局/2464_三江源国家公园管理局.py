from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2464", "page_type": "人物列表完整页", "structure_group": "sanjiangyuan_leader_three_field_cards_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_sanjiangyuan_leader_three_field_cards_v1",
    "leader_region_selector": "div#app a[href^='/ldzc/']", "name_selector": ":scope div:nth-of-type(1)", "duty_selector": ":scope div:nth-of-type(3)", "detail_link_selector": "div#app a[href^='/ldzc/']",
    "content_scope": {"start_anchor": "领导之窗", "end_anchor": "", "include_selectors": ["div#app"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "direct_links", "detail_collector_type": "static_http", "detail_link_selector": "div#app a[href^='/ldzc/']", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "同一href前缀包含栏目自链接；仅接受路径为/ldzc/具体html且卡片具备姓名、机构展示、职务三个直接文本字段", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_three_field_detail_cards",
    "locator": {"css": {"leader_region_selector": "div#app a[href^='/ldzc/']", "field_order": ["name", "displayed_organization", "duty"]}, "api": {"enabled": False, "reason": "原始HTML直接提供领导卡片和详情链接"}, "migration": {"source": "legacy_business_source_and_old_row_shape_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(page_rule["leader_region_selector"]):
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if not re.fullmatch(r"/ldzc/[^/]+\.html", urlparse(detail_url).path):
            continue
        parts = [clean_text(node.get_text(" ", strip=True)) for node in anchor.select("div")]
        parts = [part for part in parts if part]
        if len(parts) != 3:
            continue
        name = parts[0].replace(" ", "")
        duty = parts[2]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=ldzc_detail_cards；fields=first_and_third_div；order=dom"})
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

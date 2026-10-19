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
    "rule_id": "3147", "page_type": "人物列表完整页", "structure_group": "ydcmdei_body_title_value_pair_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_ydcmdei_body_title_value_pair_v1",
    "leader_region_selector": ".body:has(.title_label):has(.value_label)", "name_selector": ".title_label", "duty_selector": ".value_label", "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "Copyright", "include_selectors": [".body"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "姓名节点存在不换行空格，仅做字符间排版空格清理", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_body_title_value_pair",
    "locator": {"css": {"leader_region_selector": ".body:has(.title_label):has(.value_label)", "name_selector": ".title_label", "duty_selector": ".value_label"}, "api": {"enabled": False, "reason": "原始HTML直接提供姓名与职务成对强字段"}, "migration": {"source": "legacy_business_source_and_unused_detail_fields_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in soup.select(".body"):
        name_node = block.select_one(".title_label")
        duty_node = block.select_one(".value_label")
        if name_node is None or duty_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；leader=.body；name=.title_label；duty=.value_label；order=dom"})
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

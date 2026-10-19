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
    "rule_id": "0741", "page_type": "人物列表完整页", "structure_group": "gqb_leader_title_spacing_boundary_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_gqb_leader_title_spacing_boundary_v1",
    "leader_region_selector": ".left_list_hjpd_bt", "name_selector": "text_before_multi_space_boundary", "duty_selector": "text_after_multi_space_boundary", "detail_link_selector": "",
    "content_scope": {"start_anchor": "国务院侨务办公室", "end_anchor": "Copyright", "include_selectors": [".left_list_hjpd_bt"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "领导信息使用全角空格分隔姓名字符及姓名与职务，必须限定唯一标题块并按连续空格边界拆分", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_title_multi_space_boundary",
    "locator": {"css": {"leader_region_selector": ".left_list_hjpd_bt", "row_pattern": "姓名字符空格+多空格边界+完整职务"}, "api": {"enabled": False, "reason": "原始HTML唯一领导标题块直接提供姓名与职务"}, "migration": {"source": "legacy_business_source_and_entry_detail_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for block in soup.select(page_rule["leader_region_selector"]):
        raw_text = block.get_text(" ", strip=True).replace("\u3000", " ").replace("\xa0", " ")
        parts = re.split(r"\s{2,}", raw_text.strip(), maxsplit=1)
        if len(parts) != 2:
            continue
        name = clean_text(parts[0]).replace(" ", "")
        duty = clean_text(parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=left_list_hjpd_bt；boundary=multi_space；order=dom"})
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

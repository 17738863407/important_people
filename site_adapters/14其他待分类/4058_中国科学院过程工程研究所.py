from __future__ import annotations

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
    "rule_id": "4058", "page_type": "研究所领导简介页", "structure_group": "ipe_title_name_dess_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_ipe_title_name_dess_v1",
    "leader_region_selector": "h5.title:has(.name):has(.dess)", "name_selector": ".name > a", "duty_selector": ".dess", "detail_link_selector": ".name > a[href$='.html']",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "版权所有", "include_selectors": ["h5.title:has(.name):has(.dess)"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "card_link"}, "risk_flag": "简介文字不参与职务抽取，仅采用同一标题行。", "confidence": "high", "profile_reusable": False,
    "profile_judgement": "已核验5行name链接与dess职务字段。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "h5.title:has(.name):has(.dess)"}, "api": {"enabled": False, "reason": "HTML正文完整"}, "migration": {"verified_status": "verified"}},
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for title in soup.select("h5.title:has(.name):has(.dess)"):
        name_node, link, duty_node = title.select_one(".name"), title.select_one(".name > a[href]"), title.select_one(".dess")
        if name_node is None or duty_node is None:
            continue
        name, duty = name_node.get_text(" ", strip=True), duty_node.get_text(" ", strip=True)
        if 2 <= len(name) <= 4 and name.isalpha() and duty:
            detail_url = link["href"] if link is not None else ""
            rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": str(page_rule["parser"]), "selector_summary": "领导h5.title的name与dess"})
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

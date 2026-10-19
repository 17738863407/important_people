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
    "rule_id": "4057", "page_type": "研究中心领导简介页", "structure_group": "rcees_leader_li_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_rcees_leader_li_v1",
    "leader_region_selector": "li > .pep-txt:has(h1):has(span)", "name_selector": ".pep-txt > h1", "duty_selector": ".pep-txt > span", "detail_link_selector": "",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "院内单位", "include_selectors": ["li:has(> .pep-txt > h1):has(> .pep-txt > span)"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "页面为单页锚点简介，不把入口锚点当作独立详情页。", "confidence": "high", "profile_reusable": False,
    "profile_judgement": "已核验5个领导简介li，h1与紧邻span为当前姓名和职务。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "li:has(> .pep-txt > h1):has(> .pep-txt > span)"}, "api": {"enabled": False, "reason": "HTML简介完整"}, "migration": {"verified_status": "verified"}},
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("li:has(> .pep-txt > h1):has(> .pep-txt > span)"):
        text = item.select_one(".pep-txt > h1").get_text("", strip=True)
        name = re.sub(r"\s+", "", text)
        duty = item.select_one(".pep-txt > span").get_text(" ", strip=True)
        if 2 <= len(name) <= 4 and name.isalpha() and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule["parser"]), "selector_summary": "领导简介li的h1与span"})
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

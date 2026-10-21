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
    "rule_id": "4376",
    "page_type": "研究所现任领导图文表格页",
    "structure_group": "cas_semi_current_leader_tables",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cas_semi_current_leaders_v1",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": ".trs_editor_view table:nth-of-type(-n+2) td p:last-child",
    "duty_selector": ".trs_editor_view table:nth-of-type(-n+2) td p:first-child",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文后部另列党委和纪委委员，现任所领导仅位于前两张图文表格",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验前两张表格为现任所领导卡片，后续班子名单不纳入",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".trs_editor_view", "name_selector": ".trs_editor_view table:nth-of-type(-n+2) td p:last-child", "duty_selector": ".trs_editor_view table:nth-of-type(-n+2) td p:first-child", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "现任所领导直接呈现在HTML图文表格中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2002\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".trs_editor_view")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table in root.select("table")[:2]:
        for cell in table.select("td"):
            paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in cell.select("p")]
            paragraphs = [text for text in paragraphs if text]
            if len(paragraphs) < 2:
                continue
            match = re.match(r"^([\u3400-\u9fff·]{2,5})(?:\s+(.+))?$", paragraphs[-1])
            if match is None:
                continue
            name = match.group(1)
            trailing_title = clean_text(match.group(2) or "")
            duty = paragraphs[-2].replace(" ", "")
            if trailing_title:
                duty = f"{duty}；{'；'.join(trailing_title.split())}"
            if name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".trs_editor_view前两张领导图文表格"})
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

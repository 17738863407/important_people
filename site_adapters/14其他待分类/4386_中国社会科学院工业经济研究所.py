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
    "rule_id": "4386",
    "page_type": "研究所现任领导表格页",
    "structure_group": "cass_iie_current_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cass_iie_current_leaders_v1",
    "leader_region_selector": "table.MsoTableGrid",
    "name_selector": "table.MsoTableGrid tr td:nth-child(2) a[href]",
    "duty_selector": "table.MsoTableGrid tr td:nth-child(2) p span",
    "detail_link_selector": "table.MsoTableGrid tr td:nth-child(2) a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["table.MsoTableGrid"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "row_link"},
    "risk_flag": "页面下方另列历任所长，限定现任领导图文表格",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验现任领导表格四行及详情链接",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "table.MsoTableGrid", "name_selector": "table.MsoTableGrid tr td:nth-child(2) a[href]", "duty_selector": "table.MsoTableGrid tr td:nth-child(2) p span", "detail_link_selector": "table.MsoTableGrid tr td:nth-child(2) a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["table.MsoTableGrid"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "现任领导姓名和职务直接呈现在HTML表格中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("table.MsoTableGrid")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in root.select("tr"):
        cells = table_row.select(":scope > td")
        if len(cells) < 2:
            continue
        link = cells[1].select_one("a[href]")
        duty_node = cells[1].select_one("p span")
        if link is None or duty_node is None:
            continue
        name = clean_text(link.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link.get("href", "")), "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": "table.MsoTableGrid现任领导行"})
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

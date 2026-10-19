from __future__ import annotations

import sys
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))


PAGE_RULE = {
    "rule_id": "4564",
    "page_type": "领导表格页",
    "structure_group": "shanghai_high_court_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_shanghai_high_court_table_v1",
    "leader_region_selector": "table.zyyld_table",
    "name_selector": "tr td:nth-of-type(2)",
    "duty_selector": "tr td:nth-of-type(5)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "按实时领导表格原序提取；表内审委会专职委员及其他委员职务均保留。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按实时领导表格顺序抽取全部院级领导。"""
    url = str(page_rule.get("url") or "").strip()
    if not url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    response = requests.get(
        url, timeout=30, verify=False,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for table_row in soup.select("table.zyyld_table tr"):
        cells = table_row.select("td")
        if len(cells) != 5:
            continue
        name = clean(cells[1].get_text(" ", strip=True))
        duty = clean(cells[4].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": str(page_rule["parser"]),
            "selector_summary": "table.zyyld_table姓名列与行政职务列",
        })
    if not rows:
        raise RuntimeError("领导表格未提取到有效院级领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()

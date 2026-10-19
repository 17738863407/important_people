from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4257",
    "page_type": "管理团队表格",
    "structure_group": "首都机场集团管理团队当前表格",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cah_leadership_v1",
    "leader_region_selector": ".gltd-list-section .table_new table",
    "name_selector": "tbody > tr > td:first-child",
    "duty_selector": "tbody > tr > td:nth-child(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "HTML同时保留注释中的旧表格，且姓名单元格有隐藏占位字符，必须只解析可见当前表格。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析当前可见管理团队表格，移除姓名中的视觉占位节点。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(".gltd-list-section .table_new table")
    if table is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for tr in table.select("tbody > tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        for hidden in cells[0].select("[style*='visibility: hidden']"):
            hidden.decompose()
        name = re.sub(r"\s+", "", cells[0].get_text(" ", strip=True))
        duty_parts = [re.sub(r"\s+", "", item) for item in cells[1].stripped_strings]
        duty = "；".join(item for item in duty_parts if item)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "当前 .gltd-list-section 管理团队表格",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

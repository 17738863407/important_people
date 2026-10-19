from __future__ import annotations
import sys
from pathlib import Path

from bs4 import BeautifulSoup

PAGE_RULE = {
    "rule_id": "2134", "page_type": "人物表格页", "structure_group": "qingdao_gov_department_leader_table_v1", "reuse_scope": "青岛政务网部门机构信息页", "load_mode": "静态HTML直出", "fetch_mode": "requests", "extract_mode": "list_direct", "collector": "static_http", "parser": "S012_qingdao_gov_ldxx_table_v1",
    "leader_region_selector": "table#table5", "name_selector": "tr > td[rowspan]:first-child", "duty_selector": "tr中职务标签后的单元格", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "同页多个table#table5；仅接受同时包含职务和个人简历的领导表", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "css", "locator": {"css": {"leader_region_selector": "table#table5", "name_selector": "tr > td[rowspan]:first-child", "duty_selector": "tr中职务标签后的单元格", "detail_link_selector": ""}},
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅解析目标领导表中“姓名｜职务｜职务值”的行。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table in soup.select("table#table5"):
        if "职务" not in table.get_text(" ", strip=True):
            continue
        for table_row in table.select("tr"):
            cells = table_row.find_all("td", recursive=False)
            if len(cells) < 3 or _clean_text(cells[1].get_text(" ", strip=True)) != "职务":
                continue
            name = _clean_text(cells[0].get_text(" ", strip=True)).replace(" ", "")
            duty = _clean_text(cells[2].get_text(" ", strip=True)).removesuffix("。")
            if not name or not duty or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule["parser"]), "selector_summary": "table#table5；姓名｜职务｜职务值"})
        if rows:
            break
    if not rows:
        raise RuntimeError("目标领导表未解析到职务行")
    return rows

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()

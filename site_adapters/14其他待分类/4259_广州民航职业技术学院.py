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
    "rule_id": "4259",
    "page_type": "学校领导表格",
    "structure_group": "广州民航职业技术学院学校领导两列表格",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_gcac_leaders_v1",
    "leader_region_selector": "table",
    "name_selector": "tr > td:nth-child(2)",
    "duty_selector": "tr > td:first-child",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面有多个导航和新闻区域，须以包含党委书记职务行的两列表格限定边界。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前学校领导表格的行顺序读取姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = next(
        (item for item in soup.select("table") if "党委书记" in item.get_text(" ", strip=True)),
        None,
    )
    if table is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for tr in table.select("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        duty = re.sub(r"\s+", "", cells[0].get_text(" ", strip=True)).rstrip("：:")
        name = re.sub(r"\s+", "", cells[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "学校领导两列表格：首列职务、次列姓名",
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

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
    "rule_id": "4249",
    "page_type": "负责人名单表格",
    "structure_group": "中国粮食经济学会负责人名单两列表格",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_chinagrain_leaders_v1",
    "leader_region_selector": "table",
    "name_selector": "td.et3",
    "duty_selector": "分组职务标题与同一行第二单元格",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "表格的组标题、姓名和补充现职分列，不能把补充信息误作下一人的职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格行序读取负责人及其对应的学会职务和原始补充现职。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_pattern = re.compile(r"^(会长|副会长|秘书长)$")
    name_pattern = re.compile(r"[\u4e00-\u9fff·]{2,8}")
    current_title = ""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for tr in soup.select("table tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        values = [re.sub(r"\s+", "", cell.get_text(" ", strip=True)) for cell in cells]
        if len(cells) == 1 or cells[0].get("colspan"):
            candidate = values[0]
            if title_pattern.fullmatch(candidate):
                current_title = candidate
            continue
        name = values[0]
        if not current_title or not name_pattern.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        extra = values[1] if len(values) > 1 else ""
        evidence = current_title if not extra else f"{current_title}；{extra}"
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": "负责人名单表格：职务标题行 + 姓名/补充现职行",
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

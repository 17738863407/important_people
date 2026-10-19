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
    "rule_id": "4111",
    "page_type": "leader_profile_list",
    "structure_group": "S4111",
    "reuse_level": "site_specific",
    "load_mode": "raw_html",
    "fetch_mode": "raw_http",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.list > dl.no_border",
    "risk_notes": "页面脚本跳转会导向不存在的“首页”，原始响应中的领导列表才是可验证页面结构。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从当前人物条目的标题行提取姓名及紧随其后的现职。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for item in soup.select(rule["leader_region_selector"]):
        title = item.select_one("dd.name_list .name .title")
        if title is None:
            continue
        match = re.match(r"^([\u4e00-\u9fff]{2,4})\s+(.+)$", title.get_text(" ", strip=True))
        if match is None:
            continue
        name, duty = match.group(1).strip(), match.group(2).strip()
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
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

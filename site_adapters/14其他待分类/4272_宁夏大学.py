from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4272",
    "page_type": "现任领导卡片列表",
    "structure_group": "宁夏大学现任领导双栏卡片",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_nxu_leaders_v1",
    "leader_region_selector": ".leader .list29",
    "name_selector": ".leader .list29 .rr .a1",
    "duty_selector": ".leader .list29 .ll",
    "detail_link_selector": ".leader .list29 a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "同一列表内含校级和党委职务，按卡片双栏结构原样保留。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前领导列表的DOM顺序提取姓名、职务和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".leader .list29 > li"):
        link = card.select_one("a[href]")
        duty_node = card.select_one(".ll")
        name_node = card.select_one(".rr .a1")
        if not link or not duty_node or not name_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "现任领导卡片左右字段"})
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

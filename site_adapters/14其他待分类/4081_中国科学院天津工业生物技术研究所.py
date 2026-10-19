from __future__ import annotations

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
    "rule_id": "4081",
    "page_type": "领导卡片页",
    "structure_group": "tib_leader_b_p_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_tib_leader_b_p_card",
    "leader_region_selector": "ul.row",
    "name_selector": "li > a > b",
    "duty_selector": "li > a > p",
    "risk_flag": "仅卡片内存在真实链接时填写详情页链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐张卡片提取，避免通用选择器把首个详情页误配给全部人员。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("ul.row > li"):
        name_node = card.select_one("a > b")
        duty_node = card.select_one("a > p")
        if name_node is None or duty_node is None:
            continue
        link_node = card.select_one("a[href]")
        rows.append(
            {
                "name": name_node.get_text(" ", strip=True),
                "duty": duty_node.get_text(" ", strip=True),
                "evidence": duty_node.get_text(" ", strip=True),
                "detail_url": urljoin(final_url, link_node["href"]) if link_node else "",
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

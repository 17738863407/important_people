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
    "rule_id": "4273",
    "page_type": "现任领导卡片列表",
    "structure_group": "宁夏医科大学现任领导双栏卡片",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_nxmu_leaders_v1",
    "leader_region_selector": ".container .list29",
    "name_selector": ".container .list29 .rr .a1",
    "duty_selector": ".container .list29 .ll",
    "detail_link_selector": ".container .list29 a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "部分人物卡片未提供详情链接（href 为当前页锚点），仅保留可验证的真实详情页。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导双栏卡片的DOM顺序提取字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".container .list29 > li"):
        link = card.select_one("a[href]")
        duty_node = card.select_one(".ll")
        name_node = card.select_one(".rr .a1")
        if not link or not duty_node or not name_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        href = link.get("href", "")
        detail_url = urljoin(base_url, href) if href and href != "#" else ""
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": page_rule["parser"], "selector_summary": "现任领导卡片左右字段"})
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

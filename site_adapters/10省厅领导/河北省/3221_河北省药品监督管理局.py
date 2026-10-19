from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3221",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".child-list.columnPage .leader-list",
    "row_selector": ".child-list.columnPage .leader-list > .leader-item",
    "name_selector": ".leader-title",
    "duty_selector": ".leader-detail > p",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "领导卡片包含图片和注释中的旧职务字段，仅解析可见标题及leader-detail直接段落。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面可见领导卡片顺序提取姓名和完整职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".child-list.columnPage .leader-list > .leader-item"):
        name_node = card.select_one(".leader-title")
        duty_nodes = card.select(".leader-detail > p")
        name = normalize_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = "".join(
            normalize_text(node.get_text(" ", strip=True)) for node in duty_nodes
        ).strip()
        if not name or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

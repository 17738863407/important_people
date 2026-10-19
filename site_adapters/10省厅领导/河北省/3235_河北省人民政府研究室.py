from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3235",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "table.box",
    "row_selector": "table.box h3",
    "name_selector": "h3",
    "duty_selector": "h3 + div",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "姓名后的简介同时包含现职和分管信息，仅取相邻div中句号前的明确现职句。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", "", text).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按表格中的姓名标题顺序提取相邻简介首句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for name_node in soup.select("table.box h3"):
        name = normalize_text(name_node.get_text(" ", strip=True))
        duty_node = name_node.find_next_sibling("div")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or duty_node is None:
            continue

        profile_text = normalize_text(duty_node.get_text(" ", strip=True))
        duty = re.split(r"[。；;]", profile_text, maxsplit=1)[0].strip()
        if not duty or "研究室" not in duty:
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

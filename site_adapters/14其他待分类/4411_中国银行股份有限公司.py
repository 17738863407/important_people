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
    "rule_id": "4411",
    "page_type": "board_member_biographies",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "同页含董事会职责、委员会名单及历史履历；仅提取本行董事简历区的16个人物标题。",
    "confidence": "high",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """从董事简历标题中拆分姓名与当前职务，不把页内锚点作为详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for heading in soup.select("p > strong > a[name]"):
        text = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
        parts = text.split(" ", 1)
        if len(parts) != 2:
            continue
        name, duty = parts
        if name and duty and "董事" in duty:
            rows.append({"name": name, "duty": duty, "detail_url": ""})
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

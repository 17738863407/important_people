from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3201",
    "page_type": "多人物详情合并页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".wrap",
    "item_selector": ".wrap h5",
    "risk_note": "每个人物块h5下含简历现任句和职责；主职务只取同块完整现任句。",
    "confidence": "high",
}


def compact_text(value: str) -> str:
    """清除浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物标题DOM顺序从各自简介块提取姓名和完整现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for heading in soup.select(page_rule["item_selector"]):
        block = heading.parent
        heading_text = re.sub(
            r"[\s\u3000\xa0]+", " ", heading.get_text(" ", strip=True)
        ).strip()
        name = heading_text.split(" ")[-1]
        block_text = compact_text(block.get_text(" ", strip=True))
        match = re.search(r"现任[^。]+。", block_text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or match is None:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": re.sub(
                    r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*",
                    "",
                    match.group(0),
                    count=1,
                ),
                "detail_url": "",
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

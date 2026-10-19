from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0535",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#ivs_content",
    "item_selector": "#ivs_content p",
    "risk_note": "正文段落按姓名、职务排列，姓名内部可能含排版空格。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """将正文排版空白统一为单个空格。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文段落顺序提取姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for paragraph in soup.select(page_rule["item_selector"]):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+((?:党组|局长|副局长).*)", text)
        if not match:
            continue

        name = re.sub(r"\s+", "", match.group(1))
        evidence = clean_text(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
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

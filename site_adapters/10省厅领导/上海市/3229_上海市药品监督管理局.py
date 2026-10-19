from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3229",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div.list-contant.resume",
    "item_selector": "div.list-contant.resume p > strong",
    "risk_note": "strong姓名后依次为人口学信息和完整现任句；入口为合并页而非独立人物详情。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按strong姓名顺序在当前人物块内查找完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for name_node in soup.select(page_rule["item_selector"]):
        name = clean_text(name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        paragraph = name_node.find_parent("p")
        if paragraph is None:
            continue
        evidence = ""
        for sibling in paragraph.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            if sibling.select_one("strong") is not None:
                break
            text = clean_text(sibling.get_text(" ", strip=True))
            match = re.search(r"现任[^。]+。", text)
            if match is not None:
                evidence = match.group(0).removeprefix("现任").strip().removesuffix("。")
                break
        if not evidence:
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

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0177",
    "page_type": "多人物详情合并页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul.leader-list",
    "item_selector": "ul.leader-list > li",
    "risk_note": "每张合并卡片含简历现任句和后续分工；人物链接均为javascript空链接。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物卡片顺序提取姓名和完整现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        name_node = item.select_one(".leader-right h2")
        if name_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True))
        item_text = clean_text(item.get_text(" ", strip=True))
        match = re.search(r"现任[^。]+。", item_text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or match is None:
            continue
        evidence = re.sub(r"^现任\s*", "", match.group(0))
        evidence = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", evidence)
        evidence = re.sub(r"[。.]$", "", evidence).strip()
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

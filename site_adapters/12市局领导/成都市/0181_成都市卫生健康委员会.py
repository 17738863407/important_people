from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0181",
    "page_type": "人物表格页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "table#c",
    "item_selector": "table#c tr",
    "risk_note": "每行依次含姓名、简历、完整现任句和工作分工；合并表格无独立详情链接。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清除浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按表格行顺序提取姓名和完整现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        text = clean_text(item.get_text("", strip=True))
        name_match = re.search(r"姓名[:：](?P<name>[\u4e00-\u9fff·]{2,8})(?=简历[:：])", text)
        duty_match = re.search(r"现任[^。]+。", text)
        if name_match is None or duty_match is None:
            continue
        evidence = re.sub(r"^现任\s*", "", duty_match.group(0))
        evidence = re.sub(
            r"[<＜(（]\s*(?:挂职|兼|主持日常工作)\s*[>＞)）]",
            "",
            evidence,
        ).removesuffix("。").strip()
        rows.append(
            {
                "name": name_match.group("name"),
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

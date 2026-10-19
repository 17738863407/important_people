from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0164",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".box3_d1 ul.intro",
    "item_selector": ".box3_d1 ul.intro > li",
    "risk_note": "机构设置页范围宽，人物仅限领导简介ul.intro；每行姓名链接和职务span一一对应。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导简介列表顺序提取姓名、职务和独立人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        link = item.select_one("a[href*='/ldjj/']")
        duty_node = item.select_one("span")
        if link is None or duty_node is None:
            continue
        name = clean_text(link.get_text(" ", strip=True))
        evidence = clean_text(duty_node.get_text(" ", strip=True))
        evidence = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", evidence)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(final_url, link.get("href", "").strip()),
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

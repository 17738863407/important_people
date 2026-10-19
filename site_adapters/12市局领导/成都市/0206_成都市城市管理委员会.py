from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0206",
    "page_type": "多人物详情合并页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul#newLeaderList",
    "item_selector": "ul#newLeaderList > li",
    "risk_note": "人物卡片含职务、分工、简历，主职务只取职务标签下一行；姓名链接为独立人物页。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清除浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def value_after(lines: list[str], label: str) -> str:
    """读取指定标签后的首个非空字段。"""
    for index, line in enumerate(lines):
        if line == label:
            return next((value for value in lines[index + 1 :] if value), "")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物卡片顺序提取姓名、职务字段和独立人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        lines = [clean_text(line) for line in item.get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            continue
        name = lines[0]
        evidence = value_after(lines, "职务：").removesuffix("。").strip()
        name_link = next(
            (
                link
                for link in item.select("a[href]")
                if clean_text(link.get_text(" ", strip=True)) == name
            ),
            None,
        )
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not evidence
            or name_link is None
        ):
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(final_url, name_link.get("href", "").strip()),
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

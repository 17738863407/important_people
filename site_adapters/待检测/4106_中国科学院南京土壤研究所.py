from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4106",
    "page_type": "leader_profile_cards",
    "structure_group": "S4106",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.tlinfo",
    "risk_notes": "人物卡片仅提供姓名链接和个人简介首段，现职位于姓名后的首个分隔字段。",
    "confidence": "high",
}


def extract_current_duty(name: str, text: str) -> str:
    """从姓名后的首句提取现职，并排除明确的学位、学历和政治面貌字段。"""
    matched = re.match(rf"^{re.escape(name)}[，,]\s*([^。]+)", text)
    if matched is None:
        return ""
    fields = [field.strip() for field in re.split(r"[，,、]", matched.group(1))]
    duties = [
        field
        for field in fields
        if field
        and field not in {"博士", "中共党员"}
        and not field.endswith(("学历", "学位"))
    ]
    return "；".join(duties)


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从当前领导卡片首段中提取姓名后的首个现职字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("div.tlinfo"):
        link = card.select_one("a[href]")
        if link is None:
            continue
        name = link.get_text(" ", strip=True)
        paragraph = card.select_one("p")
        if not name or paragraph is None:
            continue
        text = paragraph.get_text(" ", strip=True)
        duty = extract_current_duty(name, text)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(page_url, link["href"]),
            }
        )
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

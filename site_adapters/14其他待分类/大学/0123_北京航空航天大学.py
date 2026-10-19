from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "0123",
    "page_type": "职务分组名单页",
    "structure_group": "buaa_school_leader_roles",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_buaa_school_leader_roles_v1",
    "leader_region_selector": "div.xxld",
    "name_selector": "div.xxld-r span",
    "duty_selector": "div.xxld-li > b",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一人物可能同时出现在具体职务和党委常委分组，按首次出现顺序合并职务",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for card in soup.select("div.xxld div.xxld-li"):
        duty_node = card.select_one(":scope > b")
        duty_parts = [clean_text(part) for part in duty_node.stripped_strings] if duty_node else []
        duty = "；".join(part for part in duty_parts if part)
        if not duty:
            continue
        for name_node in card.select("div.xxld-r span"):
            name = clean_name(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            if name in row_by_name:
                current = row_by_name[name]
                existing_duties = current["evidence"].split("；")
                if duty not in existing_duties:
                    current["duty"] += f"；{duty}"
                    current["evidence"] += f"；{duty}"
                continue
            row = {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_buaa_school_leader_roles_v1",
            }
            row_by_name[name] = row
            rows.append(row)
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

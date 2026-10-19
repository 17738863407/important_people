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
    "rule_id": "4265",
    "page_type": "领导信息三行卡片表",
    "structure_group": "国家矿山安全监察局湖北局领导信息表格卡片",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_chinamine_hubei_leaders_v1",
    "leader_region_selector": "table",
    "name_selector": "strong",
    "duty_selector": "tr:nth-child(2) div",
    "detail_link_selector": "a.red[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "每名领导使用独立三行表格卡片，必须不误取页面其他内容表格。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前三行领导卡片表解析姓名、职务和详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for table in soup.select("table"):
        name_node = table.select_one("strong")
        duty_node = table.select_one("tr:nth-of-type(2) div")
        detail_node = table.select_one("a.red[href]")
        if name_node is None or duty_node is None or detail_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True)).rstrip("。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, detail_node["href"]),
                "parser": page_rule["parser"],
                "selector_summary": "三行领导卡片表：姓名、职务、查看详细链接",
            }
        )
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

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1809",
    "page_type": "列表转人物详情页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".html008",
    "item_selector": ".html008 li.myflex[onclick]",
    "risk_note": "列表仅含姓名；HTTP受412防护，须在线浏览器读取onclick详情的职务标题后独立字段。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清除浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按列表顺序在线读取详情页职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        name_node = item.select_one(".cont")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        link_match = re.search(r"window\.open\(['\"]([^'\"]+)", item.get("onclick", ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or link_match is None:
            continue

        detail_url = urljoin(final_url, link_match.group(1))
        result = fetch_html_with_strategy(detail_url, "online")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in detail_soup.select(".content p")
        ]
        evidence = ""
        for index, text in enumerate(paragraphs):
            if text.strip("：:") != "职务":
                continue
            evidence = next((value for value in paragraphs[index + 1 :] if value), "")
            break
        if not evidence or name not in clean_text(result.html):
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": result.final_url,
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

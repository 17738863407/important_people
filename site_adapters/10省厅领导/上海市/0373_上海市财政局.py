from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0373",
    "page_type": "人物列表完整页",
    "load_mode": "分页HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".pageList",
    "item_selector": ".pageList li",
    "risk_note": "领导名单分布在分页HTML中，必须按页码顺序完整抓取。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩人物字段中的排版空白，不改变文字语义。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_items(html: str, page_rule: dict) -> list[dict]:
    """解析单页人物列表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for item in soup.select(page_rule["item_selector"]):
        name_node = item.select_one("h5")
        duty_node = item.select_one("#ldtu p")
        if name_node is None or duty_node is None:
            continue

        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text(duty_node.get_text(" ", strip=True))
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按分页顺序在线抓取并合并全部领导名单。"""
    page_match = re.search(r"totalPage\s*:\s*(\d+)", html)
    total_pages = int(page_match.group(1)) if page_match else 1
    if total_pages < 1 or total_pages > 20:
        raise RuntimeError(f"领导分页数量异常：{total_pages}")

    html_parts = [html]
    if total_pages > 1:
        from crawler_core.fetcher import fetch_html_with_strategy

        for page_number in range(2, total_pages + 1):
            page_url = re.sub(
                r"index(?:_\d+)?\.html$",
                f"index_{page_number}.html",
                final_url,
            )
            if page_url == final_url:
                raise RuntimeError(f"无法构造领导分页地址：第{page_number}页")
            result = fetch_html_with_strategy(page_url, "raw_http")
            html_parts.append(result.html)

    rows: list[dict] = []
    for html_part in html_parts:
        rows.extend(parse_items(html_part, page_rule))
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

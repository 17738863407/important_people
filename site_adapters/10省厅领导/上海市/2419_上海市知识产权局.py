from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2419",
    "page_type": "人物目录详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".trout-region-list ul.gk-list",
    "item_selector": ".trout-region-list ul.gk-list li a[href][title]",
    "risk_note": "目录页仅含人物姓名，完整现任职务须按目录顺序在线读取详情正文。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def compact_text(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按目录顺序抓取详情并提取当前人物的完整现任原句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for link in soup.select(page_rule["item_selector"]):
        name = compact_text(link.get("title", "") or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(final_url, link.get("href", "").strip())
        result = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        title = compact_text(detail_soup.title.get_text(" ", strip=True) if detail_soup.title else "")
        if name not in title:
            raise RuntimeError(f"详情页标题未回显目录姓名：{name}")
        content = detail_soup.select_one("#ivs_content")
        if content is None:
            raise RuntimeError(f"详情页缺少正文区域：{name}")
        duty_match = re.search(r"现任[^。]*。", clean_text(content.get_text(" ", strip=True)))
        if not duty_match:
            raise RuntimeError(f"详情页缺少现任职务原句：{name}")
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": duty_match.group(0).removeprefix("现任").removesuffix("。"),
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

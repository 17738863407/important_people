from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1751",
    "page_type": "列表转人物详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".introduce_list",
    "item_selector": ".introduce_list .zfxxgk_zdgkc a.text-tag[href]",
    "risk_note": "详情.art_con首个非空段落为完整原始职务，页面中的“市民政局”前缀必须保留。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def compact_name(value: str) -> str:
    """清除姓名中的字间排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按目录顺序在线读取详情正文首个非空职务段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for link in soup.select(page_rule["item_selector"]):
        list_name = compact_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name):
            continue

        detail_url = urljoin(final_url, link.get("href", "").strip())
        result = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        title_node = detail_soup.select_one(".wip_art h1, .htitle")
        detail_name = compact_name(title_node.get_text(" ", strip=True)) if title_node else ""
        if detail_name != list_name:
            continue

        evidence = next(
            (
                clean_text(paragraph.get_text(" ", strip=True))
                for paragraph in detail_soup.select(".art_con p")
                if clean_text(paragraph.get_text(" ", strip=True))
            ),
            "",
        )
        if not evidence:
            continue
        evidence = re.sub(r"。\s*$", "", evidence)
        rows.append(
            {
                "name": list_name,
                "duty": evidence,
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

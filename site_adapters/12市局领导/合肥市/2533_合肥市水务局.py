from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2533",
    "page_type": "人物表格页",
    "structure_group": "hefei_public_duty_colon_name_table",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "playwright",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "leader_region_selector": "table.xxgk-table-list > tbody",
    "detail_link_selector": ":scope > tr > td.title-td > a.title[href]",
    "risk_flag": "人物标题使用职务、姓名合并文本，须排除序号和发布日期列",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按表格原始顺序解析“职务：姓名”标题及其人物详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("table.xxgk-table-list > tbody > tr > td.title-td > a.title[href]"):
        title = str(link.get("title") or link.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", title)
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<name>[一-鿿·]{2,4})", compact)
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if match is None or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        duty = match.group("duty")
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": match.group("name"),
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_hefei_public_duty_colon_name_table_v1",
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

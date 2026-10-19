from __future__ import annotations

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
    "rule_id": "2547",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "custom",
    "collector": "chrome_cdp",
    "parser": "custom_gansu_sthj_grouped_leader_cards_v1",
    "leader_region_selector": "#singlelist > .ldwrap",
    "name_selector": ".other > ul > li > a > p",
    "duty_selector": ".other > h2",
    "detail_link_selector": ".other > ul > li > a[href]",
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "普通HTTP及无头Playwright受412防护，需使用Chrome CDP取得当前人物区",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(text: str) -> str:
    """清理页面排版空白，不改变原始语义。"""
    return " ".join((text or "").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面分组顺序提取组标题、人物姓名及其独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for group in soup.select("#singlelist > .ldwrap .other"):
        duty_node = group.select_one("h2")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue

        for detail_link in group.select("ul > li > a[href]"):
            name_node = detail_link.select_one("p")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
            if not name or name in seen_names:
                continue

            seen_names.add(name)
            detail_url = urljoin(final_url, str(detail_link.get("href", "")))
            if detail_url.rstrip("/") == final_url.rstrip("/"):
                detail_url = ""
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "selector_summary": "#singlelist > .ldwrap内按.other分组；h2职务；li a p姓名",
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

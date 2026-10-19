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
    "rule_id": "0954",
    "page_type": "职务分组名单页",
    "structure_group": "hefei_government_grouped_leaders",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "grouped_list",
    "collector": "browser_dom",
    "leader_region_selector": "div.leader-list",
    "name_selector": "div.leader-main ul > li a[title][href]",
    "duty_selector": "div.leader-main > span.leader-tit",
    "detail_link_selector": "div.leader-main ul > li a[title][href]",
    "risk_flag": "同页含领导活动与会议新闻，只能解析领导职务分组区域",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """清理页面姓名与职务的排版空白。"""
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按职务分组及组内 DOM 顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for group in soup.select("div.leader-list > div.leader-main"):
        duty_node = group.select_one(":scope > span.leader-tit")
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for link in group.select(":scope > ul > li > a[title][href]"):
            name = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
            detail_url = urljoin(final_url, str(link.get("href") or "").strip())
            if not name or not detail_url or detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)
            rows.append(
                {
                    "order": str(len(rows) + 1),
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": str(page_rule.get("confidence") or "high"),
                    "parser": "inline_hefei_government_grouped_leaders_v1",
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

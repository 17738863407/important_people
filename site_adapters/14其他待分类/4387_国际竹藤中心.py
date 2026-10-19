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
    "rule_id": "4387",
    "page_type": "中心现任领导列表页",
    "structure_group": "icbr_current_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_icbr_current_leaders_v1",
    "leader_region_selector": ".mainContent ul.newsPageList",
    "name_selector": ".newsPageList li a[href]",
    "duty_selector": ".newsPageList li a[href]",
    "detail_link_selector": ".newsPageList li a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".mainContent ul.newsPageList"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "列表标题同时包含姓名和完整职务，日期字段不参与抽取",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验4条现任领导列表及独立详情链接",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".mainContent ul.newsPageList", "name_selector": ".newsPageList li a[href]", "duty_selector": ".newsPageList li a[href]", "detail_link_selector": ".newsPageList li a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".mainContent ul.newsPageList"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "现任领导列表直接呈现在HTML中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mainContent ul.newsPageList")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in root.select(":scope > li > a[href]"):
        match = re.match(r"^([\u3400-\u9fff·]{2,5})\s+(.+)$", clean_text(link.get_text(" ", strip=True)))
        if match is None:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link.get("href", "")), "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".mainContent ul.newsPageList领导列表"})
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

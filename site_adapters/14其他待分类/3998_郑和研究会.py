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
    "rule_id": "3998", "page_type": "研究会领导分组卡片页", "structure_group": "wti_association_leader_groups", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_wti_association_leader_groups_v1",
    "leader_region_selector": ".leader-wrap", "name_selector": ".leader-list a[title]", "duty_selector": ".leader-title .title", "detail_link_selector": ".leader-list a[href]",
    "content_scope": {"start_anchor": "研究会领导", "end_anchor": "友情链接", "include_selectors": [".leader-wrap"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "dynamic_card_link"}, "risk_flag": "人员按职务分组；职务必须由紧邻前置分组标题继承，不能混入页脚友情链接。",
    "confidence": "high", "profile_reusable": False, "profile_judgement": "已核验每个领导卡片列表紧随其职务标题并含独立人物链接。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".leader-wrap", "name_selector": ".leader-list a[title]", "duty_selector": ".leader-title .title", "detail_link_selector": ".leader-list a[href]"}, "api": {"enabled": False, "reason": "当前HTML卡片提供姓名、职务分组和详情链接"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面“职务标题—紧随卡片列表”的顺序提取研究会领导。"""
    root = BeautifulSoup(html, "html.parser").select_one(".leader-wrap")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    current_duty = ""
    for child in root.find_all(recursive=False):
        classes = child.get("class", [])
        if "leader-title" in classes:
            current_duty = clean_text(child.get_text(" ", strip=True))
            continue
        if "leader-list" not in classes or not current_duty:
            continue
        for link in child.select("a[title][href]"):
            name = clean_text(link.get("title", ""))
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                continue
            rows.append({"name": name, "duty": current_duty, "detail_url": urljoin(final_url, link["href"]), "evidence": current_duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".leader-title + .leader-list a[title]"})
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

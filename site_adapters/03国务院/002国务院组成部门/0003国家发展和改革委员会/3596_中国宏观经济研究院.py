from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3596",
    "domain": "www.amr.org.cn",
    "page_type": "现任领导职务分组列表",
    "structure_group": "amr_current_leader_dt_dd_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "current_leader_grouped_cards",
    "collector": "static_http",
    "parser": "page_amr_current_leaders_v1",
    "leader_region_selector": ".yld dl",
    "name_selector": "dd li a[href] span",
    "duty_selector": "dt",
    "detail_link_selector": "dd li a[href]",
    "detail_strategy": {"required": False, "mode": "direct_card_link", "candidate_links": []},
    "risk_flag": "exclude_former_leader_groups",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(text: str) -> str:
    """清理纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只在“现任领导”区域内按职务分组和网页顺序抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    listing = soup.select_one(".yld dl")
    if listing is None:
        return []
    rows: list[dict[str, str]] = []
    current_duty = ""
    for child in listing.find_all(["dt", "dd"], recursive=False):
        if child.name == "dt":
            current_duty = clean_text(child.get_text(" ", strip=True)).strip("：:")
            if current_duty.startswith("历任"):
                break
            continue
        if not isinstance(child, Tag) or not current_duty:
            continue
        for link in child.select("li a[href]"):
            name_node = link.select_one("span")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                continue
            rows.append({
                "name": name,
                "duty": current_duty,
                "evidence": current_duty,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.yld dl；boundary=历任；fields=dt+dd li a span",
            })
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

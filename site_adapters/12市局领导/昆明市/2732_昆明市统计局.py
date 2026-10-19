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
    "rule_id": "2732",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_stats_leadership_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_kunming_stats_leadership_groups_v2",
    "leader_region_selector": ".right.leadership .leadership-item",
    "name_selector": ".leadership-item-data a[href] p",
    "duty_selector": "h3",
    "detail_link_selector": ".leadership-item-data a[href]",
    "detail_strategy": {"required": False, "mode": "dynamic_group_links", "max_detail_links": 20},
    "risk_flag": "按职务分组和组内链接DOM顺序解析；只接受姓名节点对应的独立详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析昆明市统计局领导信息分组卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    entry_url = str(page_rule.get("url") or "") or final_url
    for group in soup.select(str(page_rule.get("leader_region_selector") or "")):
        duty_node = group.select_one("h3")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for link in group.select(".leadership-item-data a[href]"):
            name_node = link.select_one("p")
            name = _clean_text(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
            if not name:
                continue
            detail_url = urljoin(final_url or entry_url, link.get("href", "").strip())
            key = (name, duty, detail_url)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "organization": str(page_rule.get("organization") or ""),
                    "url": entry_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": page_rule.get("parser", ""),
                    "selector_summary": (
                        "strategy=custom_parse_page；group=.right.leadership .leadership-item；"
                        "duty=h3；name/detail=.leadership-item-data a[href] p"
                    ),
                }
            )
    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

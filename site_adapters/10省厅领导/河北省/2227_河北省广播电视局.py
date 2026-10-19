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
    "rule_id": "2227",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_rta_visible_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_rta_visible_leader_cards_v1",
    "leader_region_selector": ".leader-main",
    "name_selector": ".leader-text-title a",
    "duty_selector": ".leader-text p:not(.leader-text-title)",
    "detail_link_selector": ".leader-text-title a[href]",
    "content_scope": {"start_anchor": "省局领导", "end_anchor": "", "include_selectors": [".leader-main"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "person_name_link", "detail_collector_type": "static_http", "detail_link_selector": ".leader-text-title a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "源码含注释掉的历史人物卡片；BeautifulSoup只遍历当前可见leader-text元素",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".leader-main", "name_selector": ".leader-text-title a", "duty_selector": ".leader-text p:not(.leader-text-title)", "detail_link_selector": ".leader-text-title a[href]", "content_scope": {"start_anchor": "省局领导", "end_anchor": "", "include_selectors": [".leader-main"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML可见人物卡片直接含姓名、职务和详情链接"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前可见人物卡片顺序提取姓名、职务和真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".leader-main")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in scope.select(".leader-text") if scope else []:
        link = card.select_one(".leader-text-title a[href]")
        duty_node = card.select_one("p:not(.leader-text-title)")
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True)) if link else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        href = link.get("href", "").strip() if link else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, href) if href else "", "evidence": duty, "parser": "custom_hebei_rta_visible_leader_cards_v1", "selector_summary": ".leader-main当前可见.leader-text；标题链接姓名、下一p职务"})
    return rows


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

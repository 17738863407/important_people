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
    "rule_id": "0526",
    "page_type": "人物列表完整页",
    "structure_group": "xinjiang_foreign_affairs_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_foreign_affairs_leader_cards_v1",
    "leader_region_selector": ".leader_list",
    "name_selector": ".leader_list li .lead_name",
    "duty_selector": ".leader_list li .lead_level",
    "detail_link_selector": ".leader_list li a[href]",
    "content_scope": {"start_anchor": "首个领导卡片", "end_anchor": "末个领导卡片", "include_selectors": [".leader_list li"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_item_dynamic_link", "detail_collector_type": "static_http", "detail_link_selector": ".leader_list li a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "页面分两个leader_list展示领导；按文档顺序合并，业务入口与人物详情字段必须分离",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".leader_list", "name_selector": "li .lead_name", "duty_selector": "li .lead_level", "detail_link_selector": "li a[href]", "content_scope": {"start_anchor": "首卡", "end_anchor": "末卡", "include_selectors": [".leader_list li"], "exclude_selectors": []}},
        "api": {"enabled": False, "reason": "当前静态HTML卡片直接提供姓名、职务和详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按两个领导列表的文档顺序解析卡片字段。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".leader_list li"):
        name_node = item.select_one(".lead_name")
        duty_node = item.select_one(".lead_level")
        link = item.select_one("a[href]")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,16}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(base_url, str(link.get("href", ""))) if link else "", "evidence": duty, "parser": "custom_xinjiang_foreign_affairs_leader_cards_v1", "selector_summary": ".leader_list卡片；.lead_name姓名；.lead_level职务"})
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

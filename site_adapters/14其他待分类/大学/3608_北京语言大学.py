from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {"rule_id": "3608", "domain": "www.blcu.edu.cn", "page_type": "现任领导卡片",
    "structure_group": "blcu_desktop_leader_cards_2026", "reuse_scope": "single_page", "load_mode": "静态HTML直出",
    "fetch_mode": "online", "extract_mode": "desktop_leader_cards", "collector": "static_http",
    "parser": "page_blcu_current_leaders_v1", "leader_region_selector": ".box-items .lst-d4",
    "name_selector": ".lst-d4_1 > li .name", "duty_selector": ".lst-d4_1 > li .tit", "detail_link_selector": ".lst-d4_1 > li > a.con[href]",
    "detail_strategy": {"required": False, "mode": "direct_person_link", "candidate_links": []},
    "risk_flag": "desktop_region_only_avoid_mobile_duplicates", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page"}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只从桌面端现任领导区域提取，避免响应式重复节点。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".box-items .lst-d4")
    if region is None: return []
    rows: list[dict[str, str]] = []
    for item in region.select("ul.lst-d4_1 > li"):
        link, name_node, duty_node = item.select_one(":scope > a.con[href]"), item.select_one(".name"), item.select_one(".tit")
        if link is None or name_node is None or duty_node is None: continue
        name, duty = clean(name_node.get_text(" ", strip=True)), clean(duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(final_url, str(link.get("href", ""))),
                         "parser": str(page_rule.get("parser", "")),
                         "selector_summary": "strategy=custom_parse_page；region=.box-items .lst-d4；item=ul.lst-d4_1>li；fields=.tit+.name+a.con"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

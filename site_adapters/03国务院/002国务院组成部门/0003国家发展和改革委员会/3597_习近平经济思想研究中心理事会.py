from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3597",
    "domain": "www.ndrc.gov.cn",
    "page_type": "职务标题多人名单",
    "structure_group": "ndrc_trs_editor_dt_dd_names_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "duty_heading_multi_names",
    "collector": "static_http",
    "parser": "page_ndrc_council_members_v1",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "dl dd span",
    "duty_selector": "dl dt",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "verified_complete_council_list",
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
    """删除名单中的纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务分组及组内版面顺序提取全部理事会成员。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for group in region.select(":scope > dl"):
        duty_node = group.select_one(":scope > dt")
        names_node = group.select_one(":scope > dd")
        if duty_node is None or names_node is None:
            continue
        duty = clean_text(duty_node.get_text(" ", strip=True)).strip("：:")
        if duty == "理事":
            continue
        name_nodes = names_node.select(":scope > span") or [names_node]
        for name_node in name_nodes:
            name = clean_text(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                continue
            rows.append({
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.TRS_Editor；group=dl；fields=dt+dd span",
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

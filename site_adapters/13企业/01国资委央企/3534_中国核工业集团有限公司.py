from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3534",
    "page_type": "人物列表完整页",
    "structure_group": "中核集团领导班子卡片",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CnncLeaderCardParser_v2",
    "leader_region_selector": "ul.leaderList li:has(.leadName):has(.leadZw)",
    "name_selector": ".leadName",
    "duty_selector": ".leadZw, .leadZw_sub",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "HTTP请求返回412；职务分布于两个原始节点，需保留节点边界",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导班子卡片DOM顺序提取姓名及全部职务节点。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("ul.leaderList li:has(.leadName):has(.leadZw)"):
        name_node = card.select_one(".leadName")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duties = [_clean_text(node.get_text(" ", strip=True)) for node in card.select(".leadZw, .leadZw_sub")]
        duties = [duty for duty in duties if duty]
        evidence = "；".join(duties)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "leaderList卡片；leadName姓名；leadZw与leadZw_sub职务",
            }
        )
    if not records:
        raise RuntimeError("中核集团领导班子卡片未解析到人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

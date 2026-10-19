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
    "rule_id": "3462",
    "page_type": "人物列表完整页",
    "structure_group": "航空工业领导人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "AvicLeaderCardParser_v1",
    "leader_region_selector": "div.leaderitem",
    "name_selector": "h5",
    "duty_selector": "h5后的div直接子div",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务由卡片内多个并列职务行组成；按原顺序合并，不做语义补写",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按人物卡片DOM顺序解析姓名及其全部职务行。"""
    if "您的访问被阻断" in html or "BJAL 事件ID" in html:
        raise RuntimeError("航空工业网页返回访问阻断页")
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for item in soup.select("div.leaderitem"):
        name_node = item.find("h5")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        duty_box = name_node.find_next_sibling("div")
        duty_parts = [] if duty_box is None else [
            text
            for node in duty_box.find_all("div", recursive=False)
            if (text := _clean_text(node.get_text(" ", strip=True)))
        ]
        evidence = "；".join(duty_parts)
        if not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "div.leaderitem；h5姓名；相邻div中的直接子div职务行",
            }
        )
    if not records:
        raise RuntimeError("航空工业领导卡片未解析到人物记录")
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

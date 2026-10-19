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
    "rule_id": "3504",
    "page_type": "人物列表完整页",
    "structure_group": "国投管理团队卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "SdicManagementCardParser_v2",
    "leader_region_selector": ".boss-list.about-gltd .boss-list-con li:has(span):has(p)",
    "name_selector": "span",
    "duty_selector": "p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "含少数民族长姓名与中间点，按姓名节点原文校验",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按管理团队卡片DOM顺序提取姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    selector = ".boss-list.about-gltd .boss-list-con li:has(span):has(p)"
    for card in soup.select(selector):
        name_node = card.select_one("span")
        duty_node = card.select_one("p")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence:
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
                "selector_summary": "国投管理团队li；span姓名；p职务",
            }
        )
    if not records:
        raise RuntimeError("国投管理团队卡片未解析到人物记录")
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

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
    "rule_id": "3529",
    "page_type": "人物列表完整页",
    "structure_group": "中咨公司管理团队成员卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "CieccManagementCardParser_v1",
    "leader_region_selector": ".chengyuan:has(> .name)",
    "name_selector": ":scope > .name",
    "duty_selector": ":scope > span:not(.name)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "部分人物职务拆分为多个同级span，需按原节点顺序完整保留",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按管理团队成员卡片顺序提取姓名与全部原始职务节点。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".chengyuan:has(> .name)"):
        name_node = card.select_one(":scope > .name")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duties = [
            _clean_text(node.get_text(" ", strip=True))
            for node in card.select(":scope > span:not(.name)")
        ]
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
                "selector_summary": "chengyuan管理团队卡片；name姓名；其余同级span为职务",
            }
        )
    if not records:
        raise RuntimeError("中咨公司管理团队卡片未解析到人物记录")
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

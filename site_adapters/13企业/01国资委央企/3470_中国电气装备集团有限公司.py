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
    "rule_id": "3470",
    "page_type": "人物列表完整页",
    "structure_group": "中国电气装备管理团队人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CeeGroupManagementCardParser_v2",
    "leader_region_selector": ".gltd .gltdk1",
    "name_selector": ".name",
    "duty_selector": ".zw",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面含移动端隐藏重复卡片；排除当前节点及祖先display:none后按可见DOM顺序提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _is_hidden(node) -> bool:
    current = node
    while current is not None and getattr(current, "name", None):
        style = (current.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or current.has_attr("hidden"):
            return True
        if str(current.get("aria-hidden", "")).lower() == "true":
            return True
        current = current.parent
    return False


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按可见管理团队卡片顺序解析姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".gltd .gltdk1"):
        if _is_hidden(card):
            continue
        name_node = card.select_one(".name")
        duty_node = card.select_one(".zw")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
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
                "selector_summary": ".gltd .gltdk1可见卡片；.name姓名；.zw职务；排除隐藏祖先",
            }
        )
    if not records:
        raise RuntimeError("中国电气装备管理团队未解析到人物记录")
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

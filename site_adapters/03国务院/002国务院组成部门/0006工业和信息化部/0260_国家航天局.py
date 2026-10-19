from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0260",
    "page_type": "人物列表完整页",
    "structure_group": "领导介绍图文卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CnsaLeaderCardParser_v2",
    "leader_region_selector": "#box1 .ld_box",
    "name_selector": ".ld_xm",
    "duty_selector": ".ld_zw",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导区域源码含已注释的历史卡片，必须仅解析当前DOM元素；机构职能和组成正文不得混入",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导介绍当前卡片DOM顺序抽取姓名与完整职务节点原文。"""
    soup = BeautifulSoup(html, "html.parser")
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("#box1 .ld_box"):
        name_node = card.select_one(".ld_xm")
        duty_node = card.select_one(".ld_zw")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
        evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#box1 .ld_box；.ld_xm；.ld_zw；排除HTML注释",
            }
        )
    if not records:
        raise RuntimeError("领导介绍当前卡片未解析到人物记录")
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

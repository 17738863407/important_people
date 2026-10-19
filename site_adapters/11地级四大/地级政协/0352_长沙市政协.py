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
    "rule_id": "0352",
    "page_type": "动态人物卡片页",
    "structure_group": "单页应用领导卡片",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "ChangshaCppccLeaderCardParser_v2",
    "leader_region_selector": ".leaders-container .leader-item",
    "name_selector": ".leader-name",
    "duty_selector": ".leader-position",
    "risk_flag": "入口为单页应用，原始HTTP仅返回短壳页面，需浏览器渲染DOM",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一动态DOM中的排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按渲染后领导卡片DOM顺序读取姓名及职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one(rule["name_selector"])
        duty_node = card.select_one(rule["duty_selector"])
        name = "".join(_clean_text(name_node.get_text(" ", strip=True) if name_node else "").split())
        evidence = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        if (name, evidence) in seen:
            continue
        seen.add((name, evidence))
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".leaders-container .leader-item内姓名与职务字段",
            }
        )
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

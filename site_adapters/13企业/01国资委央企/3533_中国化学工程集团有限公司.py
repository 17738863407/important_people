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
    "rule_id": "3533",
    "page_type": "人物列表完整页",
    "structure_group": "中国化学工程领导卡片",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CncecLeaderCardParser_v2",
    "leader_region_selector": ".leadership .leader-item:has(.name):has(.position)",
    "name_selector": ".name",
    "duty_selector": ".position",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导卡片需浏览器渲染复核，定位不依赖动画状态类",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按公司领导卡片DOM顺序提取姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".leadership .leader-item:has(.name):has(.position)"):
        name_node = card.select_one(".name")
        duty_node = card.select_one(".position")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
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
                "selector_summary": "leadership领导卡片；name姓名；position职务",
            }
        )
    if not records:
        raise RuntimeError("中国化学工程集团领导卡片未解析到人物记录")
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

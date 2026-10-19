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
    "rule_id": "3989",
    "page_type": "集团领导卡片页",
    "structure_group": "cfemg_leader_members",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cfemg_leader_members_v1",
    "leader_region_selector": ".rightCon.leader-mem .mem_box",
    "name_selector": ".leaders",
    "duty_selector": ".mem_con p:not(.leaders)",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".rightCon.leader-mem"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面含导航及空白占位li，限定集团领导容器",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验集团领导卡片HTML结构",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".rightCon.leader-mem .mem_box",
            "name_selector": ".leaders",
            "duty_selector": ".mem_con p:not(.leaders)",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".rightCon.leader-mem"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "页面直接呈现集团领导姓名和职务"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按集团领导卡片DOM顺序提取姓名和当前职务。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".rightCon.leader-mem .mem_box")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in root.select(":scope > li"):
        name_node = card.select_one(".leaders")
        paragraphs = card.select(".mem_con > p")
        if name_node is None or len(paragraphs) < 2:
            continue
        name = clean_text(name_node.get_text(" ", strip=True))
        duty_lines = [clean_text(line) for line in paragraphs[1].stripped_strings]
        duty_lines = [line for line in duty_lines if line and line != "中国财经出版传媒集团"]
        duty = "；".join(duty_lines)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".rightCon.leader-mem .mem_box>li：.leaders + .mem_con>p",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

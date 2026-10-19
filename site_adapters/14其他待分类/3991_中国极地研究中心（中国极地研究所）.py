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
    "rule_id": "3991",
    "page_type": "研究中心领导列表页",
    "structure_group": "pric_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_pric_leader_list_v1",
    "leader_region_selector": ".page-content-rg .zxld-content",
    "name_selector": ".zxld-item h3",
    "duty_selector": ".zxld-item p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".page-content-rg .zxld-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面包含导航和弹窗简介，限定中心领导列表节点",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验中心领导列表结构及原始顺序",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".page-content-rg .zxld-content",
            "name_selector": ".zxld-item h3",
            "duty_selector": ".zxld-item p",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".page-content-rg .zxld-content"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "中心领导姓名和职务直接呈现在HTML列表中"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按中心领导列表顺序提取姓名和斜杠后的职务。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".page-content-rg .zxld-content")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in root.select(".zxld-list > .zxld-item"):
        name_node = item.select_one("h3")
        duty_node = item.select_one("p")
        if name_node is None or duty_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True)).lstrip("/ ")
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
                "selector_summary": ".page-content-rg .zxld-content>.zxld-item：h3姓名+p职务",
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

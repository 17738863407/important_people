from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3525",
    "page_type": "人物列表完整页",
    "structure_group": "chinacoal_leadership_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "field_pair",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": "ul.gsld_6 > li.f-cb:has(.name):has(.job)",
    "name_selector": ".name",
    "duty_selector": ".job",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导班子",
        "end_anchor": "",
        "include_selectors": ["ul.gsld_6"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "requests",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "同页另有董事会分组，只抽取领导班子卡片容器",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"^(?:现任|职务|现任职务)[：:]?", "", text).rstrip("。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只按领导班子卡片DOM顺序提取姓名和现任职务节点。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("ul.gsld_6 > li.f-cb:has(.name):has(.job)"):
        name_node = item.select_one(".name")
        duty_node = item.select_one(".job")
        name = re.sub(
            r"\s+",
            "",
            name_node.get_text(" ", strip=True) if name_node else "",
        )
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=css；leader=ul.gsld_6 > li.f-cb:has(.name):has(.job)；"
                    "name=.name；duty=.job；detail=页面无人物独立链接"
                ),
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

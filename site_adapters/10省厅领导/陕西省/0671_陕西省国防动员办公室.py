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
    "rule_id": "0671",
    "page_type": "人物列表完整页",
    "structure_group": "leader_card_duty_and_responsibility",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiDefenseLeaderCardParser_v1",
    "leader_region_selector": ".leader-item",
    "name_selector": ".item-name",
    "duty_selector": ".item-info首个全角逗号前文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "item-info同时包含职务与分工，只保留首个全角逗号前的职务字段",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按卡片顺序提取姓名，并从混合字段中裁出明确职务。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(".leader-item"):
        name_node = card.select_one(".item-name")
        info_node = card.select_one(".item-info")
        if name_node is None or info_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        info = _clean_text(info_node.get_text(" ", strip=True))
        duty = info.split("，", 1)[0].strip("；。 ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": ".leader-item；姓名=.item-name；职务=.item-info首个全角逗号前文本",
                "order": str(len(records) + 1),
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

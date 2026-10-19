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
    "rule_id": "3230",
    "page_type": "人物表格页",
    "structure_group": "leader_card_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShanxiDrugLeaderCardParser_v1",
    "leader_region_selector": "ul.leader-list > li.list-cell",
    "name_selector": ".jg-list-title b",
    "duty_selector": ".jg-list-text",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "confidence": "high",
    "risk_flag": "卡片没有独立人物链接，详情页链接必须留空",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_text(text: str) -> str:
    """清除页面标签间产生的排版空白，不改变职务语义。"""
    return re.sub(r"\s+", "", text or "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按页面卡片顺序提取姓名和原始职务。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("ul.leader-list > li.list-cell"):
        name_node = item.select_one(".jg-list-title b")
        duty_node = item.select_one(".jg-list-text")
        if name_node is None or duty_node is None:
            continue

        name = _compact_text(name_node.get_text("", strip=True))
        duty = _compact_text(duty_node.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
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
                "selector_summary": "ul.leader-list > li.list-cell；姓名=.jg-list-title b；职务=.jg-list-text",
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

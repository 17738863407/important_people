from __future__ import annotations

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
    "rule_id": "3469",
    "page_type": "董事会成员卡片页",
    "structure_group": "cecep_board_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".second-ldtd-module .second-ldtd-item",
    "name_selector": ".second-ldtd-item-title .news-title",
    "duty_selector": ".second-ldtd-item-subtitle",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": [".second-ldtd-module"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "仅抽取董事会成员卡片，不扩展至其他管理团队栏目",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按网页顺序解析董事会成员卡片中的姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".second-ldtd-module .second-ldtd-item"):
        name_node = card.select_one(".second-ldtd-item-title .news-title")
        duty_node = card.select_one(".second-ldtd-item-subtitle")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
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

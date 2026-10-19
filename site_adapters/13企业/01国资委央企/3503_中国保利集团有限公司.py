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
    "rule_id": "3503",
    "page_type": "职务分组名单页",
    "structure_group": "poly_named_leadership_tab_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": ".about3 .above > .item, .about3 .below > .item",
    "name_selector": ".public-botitem .c h5",
    "duty_selector": ".public-botitem .c h6",
    "risk_flag": "同页并列董事会成员和领导班子成员，必须按页签标题对应面板，只取领导班子成员",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页签标题定位并只解析“领导班子成员”面板。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    tab_nodes = soup.select(".about3 .above > .item")
    panel_nodes = soup.select(".about3 .below > .item")
    target_index = next(
        (
            index
            for index, tab in enumerate(tab_nodes)
            if _clean_text(tab.get_text(" ", strip=True)) == "领导班子成员"
        ),
        -1,
    )
    if target_index < 0 or target_index >= len(panel_nodes):
        raise ValueError("未找到与‘领导班子成员’页签对应的内容面板")
    target_panel = panel_nodes[target_index]
    rows: list[dict[str, str]] = []
    for card in target_panel.select(".public-botitem .c"):
        name_node = card.select_one("h5")
        duty_node = card.select_one("h6")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        evidence = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[一-鿿·]{2,4}", name) or not evidence:
            continue
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_poly_named_leadership_tab_cards_v1",
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

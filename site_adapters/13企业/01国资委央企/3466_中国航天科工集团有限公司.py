from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3466",
    "page_type": "职务分组名单页",
    "structure_group": "casic_board_role_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": ".vid-list",
    "name_selector": ".head .name",
    "duty_selector": ".head .infor.pc-zw",
    "risk_flag": "同卡另有移动端职务图片，仅采用当前HTML职务文本节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析董事会职务分组卡片中的姓名和职务文本。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".vid-list .head"):
        name_node = card.select_one(".name")
        duty_node = card.select_one(".infor.pc-zw")
        link_node = card.select_one("a[href]")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        evidence = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        detail_url = urljoin(final_url, link_node.get("href", "")) if link_node else ""
        if not re.fullmatch(r"[一-鿿·]{2,4}", name) or not evidence:
            continue
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_casic_board_role_cards_v1",
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

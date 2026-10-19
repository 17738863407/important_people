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
    "rule_id": "4337",
    "page_type": "现任领导卡片页",
    "structure_group": "nai_current_leader_cards_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_nai_leader_cards_v1",
    "leader_region_selector": "a.bg-mask",
    "name_selector": ".name h3",
    "duty_selector": ".name h4",
    "detail_link_selector": "a.bg-mask[href]",
    "detail_strategy": {"required": True, "mode": "card_link"},
    "risk_flag": "仅使用现任领导卡片的姓名和职务标题，不从简介中的历任职务扩展。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "explicit_card_fields",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按现任领导卡片DOM顺序提取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("a.bg-mask[href]"):
        name_node = card.select_one(".name h3")
        duty_node = card.select_one(".name h4")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, card.get("href", ""))})
    if not rows:
        raise RuntimeError("现任领导页未解析到完整领导卡片")
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

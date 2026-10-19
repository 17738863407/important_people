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
    "rule_id": "4339",
    "page_type": "学院领导卡片页",
    "structure_group": "xnai_leader_team_cards_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_xnai_leader_cards_v1",
    "leader_region_selector": ".team_t",
    "name_selector": ".team_t h5",
    "duty_selector": ".team_t .job",
    "detail_strategy": {"required": True, "mode": "ancestor_link"},
    "risk_flag": "仅抽取学院领导卡片标题字段，不从简介中的现任句扩充职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "explicit_card_fields",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按卡片DOM顺序提取学院领导。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(".team_t"):
        name_node = card.select_one("h5")
        duty_node = card.select_one(".job")
        link = card.find_parent("a", href=True)
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) and duty:
            detail_url = urljoin(final_url, link.get("href", "")) if link else ""
            rows.append({"name": name, "duty": duty, "detail_url": detail_url})
    if not rows:
        raise RuntimeError("学院领导页未解析到完整卡片")
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

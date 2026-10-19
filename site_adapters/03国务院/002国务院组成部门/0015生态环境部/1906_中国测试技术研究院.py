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
    "rule_id": "1906",
    "page_type": "人物目录详情页",
    "structure_group": "nimtt_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "field_pair",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".leader .leader_part",
    "name_selector": ".leader_mes .lin_name",
    "duty_selector": ".leader_mes .lin_zhi",
    "detail_link_selector": "a.leader_part_1[href]",
    "content_scope": {
        "include_selectors": [".leader"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "card_link",
        "detail_link_selector": "a.leader_part_1[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "仅抽取领导班子卡片，不扫描页面新闻、导航或合作链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导班子卡片DOM顺序提取姓名、原始职务和人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".leader .leader_part"):
        name_node = card.select_one(".leader_mes .lin_name")
        duty_node = card.select_one(".leader_mes .lin_zhi")
        link_node = card.select_one("a.leader_part_1[href]")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty:
            continue
        detail_url = urljoin(final_url, str(link_node.get("href") or "")) if link_node else ""
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url})
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

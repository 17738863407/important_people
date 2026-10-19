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
    "rule_id": "3545",
    "page_type": "人物列表完整页",
    "structure_group": "航天科技领导成员卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "SpaceChinaLeaderCardParser_v2",
    "leader_region_selector": ".boss-one-box > div, .boss-two-box > div, .bosss-three-box .btb3-img",
    "name_selector": "a.lan_x_12",
    "duty_selector": "a.lan_x_12",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "姓名后职务分列为多个同级链接，按原节点顺序保留且不做语义标点改写",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200b\u3000]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导成员卡片顺序提取姓名、多行职务和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    selector = ".boss-one-box > div, .boss-two-box > div, .bosss-three-box .btb3-img"
    for card in soup.select(selector):
        values = [_clean_text(node.get_text(" ", strip=True)) for node in card.select("a.lan_x_12")]
        values = [value for value in values if value]
        if len(values) < 2:
            continue
        name = re.sub(r"\s+", "", values[0])
        evidence = "；".join(values[1:])
        link_node = card.select_one("a[href]")
        detail_url = urljoin(base_url, str(link_node.get("href", ""))) if link_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": "boss领导卡片；lan_x_12首项姓名、后续项职务；卡片href详情",
            }
        )
    if not records:
        raise RuntimeError("航天科技领导成员卡片未解析到人物记录")
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

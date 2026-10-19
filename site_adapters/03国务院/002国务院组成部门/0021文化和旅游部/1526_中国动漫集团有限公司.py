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
    "rule_id": "1526",
    "page_type": "人物卡片列表页",
    "structure_group": "中国动漫集团官网领导卡片",
    "reuse_scope": "acgnet_leader_cards",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "AcgnetLeaderCardParser_v1",
    "leader_region_selector": ".p_loopitem .e_container-39",
    "name_selector": ".s_title",
    "duty_selector": ".s_summary",
    "detail_link_selector": ".s_title a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "页面包含重复的集团简介导航；只解析领导循环项内同时具备姓名标题、职务摘要和详情链接的卡片。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析集团官网领导卡片，保留页面原始排列顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(rule["leader_region_selector"])
    if not cards:
        raise RuntimeError("未找到集团官网领导卡片")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in cards:
        name_node = card.select_one(rule["name_selector"])
        duty_node = card.select_one(rule["duty_selector"])
        link_node = card.select_one(rule["detail_link_selector"])
        if name_node is None or duty_node is None or link_node is None:
            raise RuntimeError("领导卡片缺少姓名、职务或详情链接节点")
        name = _clean_text(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) is None:
            raise RuntimeError(f"领导卡片姓名格式异常：{name}")
        if not duty:
            raise RuntimeError(f"领导卡片职务为空：{name}")
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link_node.get("href", "")),
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".p_loopitem .e_container-39领导卡片；.s_title姓名；.s_summary职务",
            }
        )
    if not records:
        raise RuntimeError("集团官网领导卡片未解析到人物记录")
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

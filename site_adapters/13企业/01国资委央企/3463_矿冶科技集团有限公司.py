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
    "rule_id": "3463",
    "page_type": "人物列表完整页",
    "structure_group": "矿冶集团领导人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "BgrimmLeaderCardParser_v1",
    "leader_region_selector": "ul.BTG-list5 li",
    "name_selector": "strong.gp-f18",
    "duty_selector": "div.item-txt5",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "页面模板含浏览器升级提示字样会触发online有效性误判；使用已核验原始HTTP；仅接受当前人物卡片内链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导人物卡片顺序解析姓名、职务和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("ul.BTG-list5 li"):
        name_node = card.select_one("strong.gp-f18")
        duty_node = card.select_one("div.item-txt5")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        link = name_node.find_parent("a", href=True) or card.select_one("a[href]")
        detail_url = urljoin(base_url, str(link.get("href", ""))) if link else ""
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": "ul.BTG-list5 li；strong.gp-f18姓名；div.item-txt5职务；卡片a详情",
            }
        )
    if not records:
        raise RuntimeError("矿冶集团领导卡片未解析到人物记录")
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

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
    "rule_id": "3508",
    "page_type": "人物列表完整页",
    "structure_group": "中国石化公司管理层人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "SinopecLeaderCardParser_v2",
    "leader_region_selector": ".right_cont .leadship_item",
    "name_selector": ".zw-title",
    "duty_selector": ".zw-SubTitle",
    "detail_link_selector": ".presi_intr a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "online误把分页函数中的动态location表达式当静态跳转；raw_http保留权威列表",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按公司管理层卡片DOM顺序提取姓名、职务及独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".right_cont .leadship_item"):
        name_node = card.select_one(".zw-title")
        duty_node = card.select_one(".zw-SubTitle")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        link_node = card.select_one(".presi_intr a[href]")
        href = (link_node.get("href") or "").strip() if link_node else ""
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": (
                    ".leadship_item；.zw-title姓名；.zw-SubTitle职务；简介内a详情"
                ),
            }
        )
    if not records:
        raise RuntimeError("中国石化公司管理层卡片未解析到人物记录")
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

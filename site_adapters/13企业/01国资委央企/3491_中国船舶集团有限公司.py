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
    "rule_id": "3491",
    "page_type": "人物列表完整页",
    "structure_group": "中国船舶集团领导图文卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CsscLeaderCardParser_v2",
    "leader_region_selector": "ul.olist_pics li:has(img)",
    "name_selector": "span:first-of-type",
    "duty_selector": "span:nth-of-type(n+2)",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "部分人物职务分列于多个span，按DOM顺序完整合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip(" ，,、；;")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导图文卡片顺序提取姓名、全部职务行与人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("ul.olist_pics li:has(img)"):
        spans = card.select("span")
        if len(spans) < 2:
            continue
        name = re.sub(r"\s+", "", spans[0].get_text(" ", strip=True))
        duties = [
            cleaned
            for node in spans[1:]
            if (cleaned := _clean_text(node.get_text(" ", strip=True)))
        ]
        evidence = "；".join(duties)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        link_node = card.select_one("a[href]")
        href = (link_node.get("href") or "").strip() if link_node else ""
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": (
                    "ul.olist_pics li:has(img)；首个span姓名；其余span职务；a[href]详情"
                ),
            }
        )
    if not records:
        raise RuntimeError("中国船舶集团领导图文卡片未解析到人物记录")
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

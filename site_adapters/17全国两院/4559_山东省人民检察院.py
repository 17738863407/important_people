from __future__ import annotations

import sys
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(value: object) -> str:
    """移除姓名和职务节点中的排版空白、零宽字符。"""
    return re.sub(r"[\s\u200b\u3000\xa0]+", "", str(value or ""))


PAGE_RULE = {
    "rule_id": "4559",
    "page_type": "领导卡片列表",
    "structure_group": "shandong_procuratorate_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_shandong_procuratorate_cards_v1",
    "leader_region_selector": ".leaderList > ul > li",
    "name_selector": ".leaderLeft .xm a[href]",
    "duty_selector": ".leaderLeft .zw",
    "detail_link_selector": ".leaderLeft .xm a[href]",
    "detail_strategy": {"required": False, "mode": "same_card"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析领导卡片列表；检察委员会委员、专职检察委员等委员类人物与职务均按网页原序完整保留。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按实时领导卡片顺序抽取，包含委员类人物与职务。"""
    response = requests.get(
        str(page_rule["url"]),
        timeout=30,
        verify=False,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".leaderList > ul > li"):
        name_link = card.select_one(".leaderLeft .xm a[href]")
        duty_node = card.select_one(".leaderLeft .zw")
        name = clean(name_link.get_text(" ", strip=True) if name_link else "")
        duty_parts = [clean(text) for text in duty_node.stripped_strings] if duty_node else []
        duty = "、".join(part for part in duty_parts if part)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": urljoin(response.url, str(name_link.get("href") or "")),
            "parser": str(page_rule["parser"]),
            "selector_summary": ".leaderList卡片中的.zw职务与.xm姓名",
        })
    if not rows:
        raise RuntimeError("领导卡片未提取到人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

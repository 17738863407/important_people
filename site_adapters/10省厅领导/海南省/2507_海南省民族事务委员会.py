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


def clean_text(value: str) -> str:
    """仅做排版空白的确定性归一。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片顺序提取em姓名、span职务和卡片详情。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, card in enumerate(soup.select("a[href]:has(em):has(span)"), start=1):
        name_node = card.select_one("em")
        duty_node = card.select_one("span")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(card.get("href") or "")),
                "source_order": str(source_order),
                "confidence": "high",
                "parser": "page_inline_hainan_ethnic_em_span_cards_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2507",
    "page_type": "人物列表完整页",
    "structure_group": "海南民宗委em姓名span职务卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hainan_ethnic_em_span_cards_v2",
    "leader_region_selector": "a[href]:has(em):has(span)",
    "name_selector": "em",
    "duty_selector": "span",
    "detail_link_selector": "a[href]:has(em):has(span)",
    "detail_strategy": {"required": False, "mode": "card_link_only", "detail_collector_type": "none"},
    "risk_flag": "职务仅归一排版空白，不以旧结果补写标点或机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

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
    """压缩网页字段的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取h1姓名、h2职务及独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, item in enumerate(soup.select("ul.LdrList li"), start=1):
        link = item.select_one("h1 a[href]")
        duty_node = item.select_one("h2")
        name = clean_text(link.get_text(" ", strip=True) if link else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip(" ：:，,。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_guizhou_cdc_leader_cards_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1150",
    "page_type": "人物列表完整页",
    "structure_group": "贵州疾控局领导h1-h2卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_guizhou_cdc_leader_cards_v2",
    "leader_region_selector": "ul.LdrList",
    "name_selector": "ul.LdrList li h1 a[href]",
    "duty_selector": "ul.LdrList li h2",
    "detail_link_selector": "ul.LdrList li h1 a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "card_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "卡片含长篇负责与分管文本，证据严格限定h2职务字段",
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

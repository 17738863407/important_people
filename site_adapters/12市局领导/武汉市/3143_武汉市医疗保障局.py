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


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析武汉市医疗保障局领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for card in soup.select("ul.info-list li.ldxx-li"):
        h3_nodes = card.select(".ldxx-li-right h3")
        if len(h3_nodes) < 2:
            continue
        name = _clean_text(h3_nodes[0].get_text(" ", strip=True))
        position = _clean_text(h3_nodes[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not position:
            continue
        link = card.select_one("a.ldxx-details[href]")
        detail_url = urljoin(base_url, link.get("href", "")) if link else ""
        records.append(
            {
                "name": name,
                "duty": position,
                "detail_url": detail_url,
                "evidence": position,
                "confidence": "high",
                "parser": "page_inline_wuhan_healthcare_leader_cards_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "3143",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_healthcare_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_wuhan_healthcare_leader_cards_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "人物卡片另含主持、分管和联系范围，依据说明仅取第二个 h3 的原始职务",
    "confidence": "high",
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

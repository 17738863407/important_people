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
    "rule_id": "0097",
    "page_type": "图片名单型",
    "structure_group": "image_card_with_html_text",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiAtcmLeaderCardParser_v1",
    "leader_region_selector": ".w-leader0img",
    "name_selector": ".w-name",
    "duty_selector": ".w-posi",
    "detail_link_selector": "ancestor a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "confidence": "high",
    "risk_flag": "头像与人物信息同卡片展示，优先使用图片旁可验证HTML文本",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按人物卡片顺序提取图片旁的结构化HTML姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".w-leader0img"):
        name_node = card.select_one(".w-name")
        duty_node = card.select_one(".w-posi")
        if name_node is None or duty_node is None:
            continue

        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        if not duty or name in seen:
            continue

        parent_link = card.find_parent("a", href=True)
        detail_url = urljoin(base_url, parent_link.get("href", "")) if parent_link else ""
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": ".w-leader0img；姓名=.w-name；职务=.w-posi；详情=祖先a[href]",
                "order": str(len(records) + 1),
            }
        )

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

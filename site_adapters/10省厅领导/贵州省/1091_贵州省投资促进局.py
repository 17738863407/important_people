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
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按右侧领导简介目录顺序提取卡片姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select(".ldzc_right li a[href][title]"), start=1):
        name = clean_text(str(link.get("title") or "")).replace(" ", "")
        field = link.select_one("p")
        values = [clean_text(item) for item in field.stripped_strings] if field else []
        duty = clean_text(" ".join(values[1:])) if len(values) > 1 else ""
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_guizhou_invest_leader_cards_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1091",
    "page_type": "人物列表完整页",
    "structure_group": "贵州投资促进局右侧领导简介卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_guizhou_invest_leader_cards_v2",
    "leader_region_selector": ".ldzc_right",
    "name_selector": ".ldzc_right li a[title]",
    "duty_selector": ".ldzc_right li a p姓名后文本",
    "detail_link_selector": ".ldzc_right li a[href][title]",
    "detail_strategy": {
        "required": False,
        "mode": "card_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "正文左侧仅显示当前人物，完整人物范围须限定右侧领导简介目录",
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

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩人物简介中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在每个人物简介卡片内提取姓名及完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, card in enumerate(soup.select("#cona_TBABa_2 .zx-ldjs-824"), start=1):
        text = re.sub(r"^个人简介", "", clean_text(card.get_text(" ", strip=True)))
        name_match = re.match(r"([\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if not name_match or not evidence_match:
            continue
        name = name_match.group(1)
        evidence = evidence_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "source_order": str(source_order),
                "confidence": "high",
                "parser": "page_inline_hainan_jgj_profile_cards_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1121",
    "page_type": "多人物详情合并页",
    "structure_group": "海南机关事务局人物简介卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hainan_jgj_profile_cards_v2",
    "leader_region_selector": "#cona_TBABa_2 .zx-ldjs-824",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "merged_profiles_no_independent_detail",
        "detail_collector_type": "none",
    },
    "risk_flag": "仅在各人物简介卡片内提取开头姓名及完整现任句，不读取分工或管理后台编辑链接",
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

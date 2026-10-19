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


PAGE_RULE = {
    "rule_id": "3531",
    "page_type": "人物列表完整页",
    "structure_group": "招商局管理团队卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "CmhkManagementCardParser_v2",
    "leader_region_selector": "ul.gsglc_ul > li:has(.gsglc_ul_right_top i)",
    "name_selector": ".gsglc_ul_right_top i",
    "duty_selector": ".gsglc_ul_right_top i",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "卡片同时含现任简介和历史履历，依据说明仅取顶部明确职务字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按管理团队卡片DOM顺序提取顶部姓名与职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("ul.gsglc_ul > li:has(.gsglc_ul_right_top i)"):
        values = [_clean_text(node.get_text(" ", strip=True)) for node in card.select(".gsglc_ul_right_top i")]
        values = [value for value in values if value]
        if len(values) < 2:
            continue
        name, evidence = values[0], values[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "gsglc管理团队卡片；顶部首两个i分别为姓名、职务",
            }
        )
    if not records:
        raise RuntimeError("招商局集团管理团队卡片未解析到人物记录")
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

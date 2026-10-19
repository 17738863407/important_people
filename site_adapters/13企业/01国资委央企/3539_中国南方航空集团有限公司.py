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
    "rule_id": "3539",
    "page_type": "人物列表完整页",
    "structure_group": "南航集团领导团队卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "CsairGroupTeamCardParser_v2",
    "leader_region_selector": ".team4 dl.dl_list12:has(.list12_t):has(.dds)",
    "name_selector": ".list12_t",
    "duty_selector": ".dds",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一卡片并列集团与股份公司多行职务，仅保留目标集团原始职务行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200b\u3000]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导团队卡片顺序提取姓名与目标集团的全部原始职务行。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    organization = "中国南方航空集团有限公司"
    for card in soup.select(".team4 dl.dl_list12:has(.list12_t):has(.dds)"):
        name_node = card.select_one(".list12_t")
        duty_node = card.select_one(".dds")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        lines = [_clean_text(text) for text in duty_node.get_text("\n", strip=True).splitlines()]
        duties = [line for line in lines if organization in line]
        evidence = "；".join(duties)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "team4领导卡片；list12_t姓名；dds内含集团全称的职务行",
            }
        )
    if not records:
        raise RuntimeError("南航集团领导团队卡片未解析到人物记录")
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

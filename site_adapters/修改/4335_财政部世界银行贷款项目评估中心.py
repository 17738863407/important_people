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
    "rule_id": "4335",
    "page_type": "财政部领导简介混合机构页",
    "structure_group": "mof_gjs_center_leader_row_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_mof_center_leader_v1",
    "leader_region_selector": "p:has(span)",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时含国际财金合作司领导，仅保留明确写有世界银行贷款项目评估中心的行。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "organization_bound_row",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """提取明确归属于项目评估中心的领导行。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        matched = re.fullmatch(
            r"([\u3400-\u9fff·]{2,8})\s+(世界银行贷款项目评估中心.+)", text
        )
        if matched:
            rows.append({"name": matched.group(1), "duty": matched.group(2), "detail_url": ""})
    if not rows:
        raise RuntimeError("未找到明确归属于世界银行贷款项目评估中心的领导行")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

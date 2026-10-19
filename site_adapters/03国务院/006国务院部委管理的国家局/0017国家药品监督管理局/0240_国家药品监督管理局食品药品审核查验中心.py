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
    "rule_id": "0240",
    "page_type": "中心领导姓名职务卡片",
    "structure_group": "cfdi_center_leader_cells",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_cfdi_center_leaders_v1",
    "leader_region_selector": ".zxLeader",
    "name_selector": ".zlCell label",
    "duty_selector": ".zlCell span",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "中心领导",
        "end_anchor": "中心职责",
        "include_selectors": [".zxLeader"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页包含大量中心职责和处室说明，只允许解析中心领导专属卡片区域",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩HTML节点中的全角空格与其他排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页卡片原始顺序提取中心领导。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zxLeader")
    if region is None:
        raise RuntimeError("未找到中心领导区域：.zxLeader")

    rows: list[dict[str, str]] = []
    for item in region.select(".zlCell"):
        name_node = item.select_one("label")
        duty_node = item.select_one("span")
        if name_node is None or duty_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": str(page_rule.get("parser", "")),
                }
            )
    if not rows:
        raise RuntimeError("中心领导区域未提取到有效人物")
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

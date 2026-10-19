from __future__ import annotations

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3134",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_medical_security_leader_table_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanjing_medical_security_leader_table_v3",
    "leader_region_selector": "#nsks table tbody",
    "name_selector": "#nsks tr td:nth-of-type(1)",
    "duty_selector": "#nsks tr td:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "领导分工位于隐藏页签#nsks的三列表格，第三列为职责分工而非职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#nsks", "row_selector": "#nsks table tbody tr"},
        "api": {"enabled": False, "reason": "#nsks领导三列表格由当前页面HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的中文排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#nsks三列表格的网页顺序提取姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#nsks")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in region.select("table tbody tr"):
        cells = table_row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        name = normalize_layout(cells[0].get_text(" ", strip=True)).replace(" ", "")
        evidence = normalize_layout(cells[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,12}", name) or not evidence:
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#nsks table tbody tr按DOM顺序提取第一列姓名与第二列职务；第三列职责不进入依据说明",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

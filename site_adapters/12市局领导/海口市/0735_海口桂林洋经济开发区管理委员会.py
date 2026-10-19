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
    "rule_id": "0735",
    "page_type": "人物表格页",
    "structure_group": "haikou_gly_leader_word_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "haikou_gly_leader_table_present_sentence_v1",
    "leader_region_selector": "#ContentRegion table.MsoTableGrid",
    "name_selector": "tr > td:first-child",
    "duty_selector": "tr > td:nth-child(2)",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名",
        "end_anchor": "",
        "include_selectors": ["#ContentRegion table.MsoTableGrid"],
        "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "Word导出表格存在中文词组内部排版空格；仅第二列完整现任句可作为职务依据，第三列分工不得写入",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "2026-08-08在线验证#ContentRegion内唯一MsoTableGrid表格共5个人物行",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#ContentRegion table.MsoTableGrid",
            "name_selector": "tr > td:first-child",
            "duty_selector": "tr > td:nth-child(2)",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "姓名",
                "end_anchor": "",
                "include_selectors": ["#ContentRegion table.MsoTableGrid"],
                "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
            },
        },
        "api": {"enabled": False, "reason": "HTTP 200静态HTML已完整包含权威人物表格"},
    },
}


def clean_text(value: str) -> str:
    """压缩网页排版空白，并合并中文词组内部的Word排版断空格。"""
    text = str(value or "").replace("\u3000", " ").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s+([，。；：、！？）】])", r"\1", text)


def extract_present_sentence(profile_text: str) -> str:
    """仅返回当前人物基本信息单元格中的完整“现任……”原句。"""
    match = re.search(r"现任[^。]*。", clean_text(profile_text))
    return match.group(0) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析海口桂林洋经济开发区领导班子强结构表格。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#ContentRegion table.MsoTableGrid")
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；table=#ContentRegion table.MsoTableGrid；"
        "name=第1列；evidence=第2列完整现任句；detail=none"
    )
    for table_row in table.select("tr"):
        cells = table_row.select("td, th")
        if len(cells) < 3:
            continue
        name = clean_text(cells[0].get_text(" ", strip=True))
        if name == "姓名" or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        evidence = extract_present_sentence(cells[1].get_text(" ", strip=True))
        duty = evidence.removeprefix("现任").rstrip("。") if evidence else ""
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

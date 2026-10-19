from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4279", "page_type": "现任领导表格", "structure_group": "宁夏建设职业技术学院现任领导两列表", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_nxjy_leaders_v1", "leader_region_selector": "#vsb_content table.MsoNormalTable", "name_selector": "#vsb_content table.MsoNormalTable tr td:first-child", "duty_selector": "#vsb_content table.MsoNormalTable tr td:nth-child(2)", "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "页面正文只有姓名、职务两列表，需跳过表头且不扫描页外文本。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前领导表格行序提取姓名和职务。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#vsb_content table.MsoNormalTable")
    if not table:
        return []
    rows: list[dict[str, str]] = []
    for tr in table.select("tr"):
        cells = tr.select(":scope > td")
        if len(cells) != 2:
            continue
        name = re.sub(r"\s+", "", cells[0].get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", cells[1].get_text(" ", strip=True))
        if name != "姓名" and duty != "职务" and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "现任领导两列表"})
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

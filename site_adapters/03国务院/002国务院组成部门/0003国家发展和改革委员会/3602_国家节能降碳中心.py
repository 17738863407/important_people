from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3602", "domain": "www.chinanecc.cn", "page_type": "侧栏领导表格",
    "structure_group": "chinanecc_sidebar_leader_table_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "table_duty_name_inherit",
    "collector": "static_http", "parser": "page_chinanecc_leaders_v1", "leader_region_selector": ".l_b1 .cont1 table",
    "name_selector": "tr td:nth-of-type(2)", "duty_selector": "tr td:nth-of-type(1)", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "blank_duty_cells_inherit_previous", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """删除表格单元格中的纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格行序抽取，空职务单元格继承上一行职务。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(".l_b1 .cont1 table")
    if table is None:
        response = requests.get(str(page_rule.get("url", "")), timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.select_one(".l_b1 .cont1 table")
    if table is None: return []
    rows: list[dict[str, str]] = []
    duty = ""
    for row in table.select("tr"):
        cells = row.select(":scope > td")
        if len(cells) < 2: continue
        duty = clean(cells[0].get_text(" ", strip=True)) or duty
        name = clean(cells[1].get_text(" ", strip=True))
        if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                         "parser": str(page_rule.get("parser", "")),
                         "selector_summary": "strategy=custom_parse_page；region=.l_b1 .cont1 table；row=tr；fields=td[1]+td[2]；blank-duty=inherit"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

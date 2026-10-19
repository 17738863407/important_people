from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按法院领导表格原始行序提取职务和姓名。"""
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.select_one(".court-info-box-wrap .leader-tb")
    if table is None:
        raise RuntimeError("未找到法院领导表格 .leader-tb")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for tr in table.select("tr"):
        duty_node = tr.select_one("td.leader-l")
        name_node = tr.select_one("td.leader-r")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip("，,。；; ")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".leader-tb原始行序；td.leader-l职务、td.leader-r姓名；javascript占位链接不作详情页",
            }
        )
        seen.add(name)
    if not rows:
        raise RuntimeError("法院领导表格未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4524",
    "domain": "www.fjcourt.gov.cn",
    "page_type": "法院领导表格",
    "structure_group": "fujian_high_court_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "table_rows",
    "parser": "page_fujian_high_court_leader_table_v1",
    "leader_region_selector": ".court-info-box-wrap .leader-tb",
    "name_selector": "tr td.leader-r",
    "duty_selector": "tr td.leader-l",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "相邻页签为审判委员会和机构设置；只解析当前领导表格，表内委员和专职委员均保留，javascript占位链接留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

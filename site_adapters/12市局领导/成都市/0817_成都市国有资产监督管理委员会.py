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
    "rule_id": "0817",
    "page_type": "人物列表完整页",
    "structure_group": "chengdu_gzw_leader_name_duty_list",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "chrome_cdp",
    "parser": "V007_text_name_space_duty_v1",
    "leader_region_selector": "div.leadInfo_box",
    "risk_flag": "人物行是姓名与职务同行文本，无独立详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict):
    """复用既有姓名空格职务解析，仅清理当前页依据说明。"""
    from crawler_core.parsers_v1 import name_space_duty_parser_v1

    rows = name_space_duty_parser_v1(page_rule, html, final_url)
    for row in rows:
        row.evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", row.duty).strip()
        row.duty = row.evidence
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

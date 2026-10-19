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
    "rule_id": "3556",
    "page_type": "百度百科半结构领导栏目",
    "load_mode": "动态DOM渲染",
    "extraction_mode": "半结构分组解析",
    "parser": "S027_baidu_baike_leader_section_v1",
    "baike_section_titles": ["现任领导"],
    "confidence": "高",
    "risk_notes": "仅解析现任领导栏目，并在单页内排除现职句后的身份佐证、简历和人口学信息。",
}


def _current_duty(value: object) -> str:
    """从当前人物条目中保留首个现职句，排除其后的简历或活动佐证。"""
    text = str(value or "").strip()
    text = text.split("。", maxsplit=1)[0]
    text = re.split(r"，于\d{4}年", text, maxsplit=1)[0]
    return text.strip(" ：:，,、；;。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """复用百度百科现任领导栏目解析，并执行本页证据边界清洗。"""
    from crawler_core.baidu_baike import parse_baidu_baike_leader_section_v1

    rows = parse_baidu_baike_leader_section_v1(page_rule, html, final_url, None)
    for row in rows:
        row.duty = _current_duty(row.duty)
        row.evidence = row.duty
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"执行形态：{runtime_context.get('execution_mode', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

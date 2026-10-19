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
    "rule_id": "3568",
    "page_type": "配图后职务姓名表格页",
    "structure_group": "spp_department_duty_name_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom table",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名单元格混用多人分隔空格与二字姓名内部字距",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def _split_names(value: str) -> list[str]:
    """拆分姓名列表，并合并由排版字距拆开的二字姓名。"""
    tokens = [
        token
        for token in re.split(r"[\s、，,；;]+", _clean_text(value))
        if token
    ]
    names: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if (
            len(token) == 1
            and index + 1 < len(tokens)
            and len(tokens[index + 1]) == 1
        ):
            token += tokens[index + 1]
            index += 1
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", token):
            names.append(token)
        index += 1
    return names


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐行解析正文中的职务、姓名两列表格。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for row in region.select("table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != 2:
            continue
        duty = _clean_text(cells[0].get_text(" ", strip=True)).strip(" ：:")
        if not duty:
            continue
        for name in _split_names(cells[1].get_text(" ", strip=True)):
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=duty,
                    detail_url="",
                    evidence=duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary="#fontzoom表格行中的第一列职务与第二列姓名",
                )
            )

    return records


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=update_fetch_memory,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"执行形态：{runtime_context.get('execution_mode', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)

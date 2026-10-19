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
    "rule_id": "3569",
    "page_type": "人物配图与职务姓名双栏混排页",
    "structure_group": "spp_department_span_pairs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "部分人物有配图，后续内设部门负责人仅以职务姓名双栏列出",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def _clean_name(value: str) -> str:
    """删除姓名节点中的排版字距。"""
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序解析职务、姓名成对浮动节点。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in region.find_all("p", recursive=False):
        spans = paragraph.find_all("span", recursive=False)
        if len(spans) != 2:
            continue
        duty = _clean_text(spans[0].get_text(" ", strip=True)).strip(" ：:")
        name = _clean_name(spans[1].get_text(" ", strip=True))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
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
                selector_summary="#fontzoom直属段落中的第一列职务span与第二列姓名span",
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

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
    "rule_id": "3583",
    "page_type": "图片后职务姓名双栏页",
    "structure_group": "spp_department_role_name_split_spans_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文含职责介绍，人物段落使用职务姓名双span字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    text = (value or "").replace("\u2002", "").replace("\u3000", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文双栏段落的原始顺序提取完整职务和姓名。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in region.find_all("p", recursive=False):
        duty_node = paragraph.select_one(":scope > .spanleft")
        name_node = paragraph.select_one(":scope > .spanright")
        if duty_node is None or name_node is None:
            continue
        duty = _clean_text(duty_node.get_text(" ", strip=True)).rstrip("：:")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        key = (name, duty)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty or key in seen:
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
                selector_summary="#fontzoom直属段落中的spanleft职务与spanright姓名",
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

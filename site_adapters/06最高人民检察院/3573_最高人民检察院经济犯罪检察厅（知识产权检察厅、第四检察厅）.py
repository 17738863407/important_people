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
    "rule_id": "3573",
    "page_type": "图片后职务姓名混排页",
    "structure_group": "spp_department_staff_text_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "检察官名单跨两个段落，第二段仅保留续行姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def _clean_duty(value: str) -> str:
    """删除字段分隔符和纯排序附注，保留网页中的实际职务表述。"""
    duty = _clean_text(value).rstrip("：:")
    duty = re.sub(r"[（(]按(?:姓名|姓氏)笔画(?:为序|排序|排列)?[）)]", "", duty)
    return duty.strip(" ：:")


def _split_names(value: str) -> list[str]:
    """按网页名单分隔符拆分中文姓名。"""
    candidates = re.split(r"[\s、，,；;]+", _clean_text(value))
    return [name for name in candidates if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文顺序解析双栏、冒号名单和紧邻的纯姓名续行。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    continuation_duty = ""

    def append_record(name: str, duty: str, selector_summary: str) -> None:
        clean_name = re.sub(r"\s+", "", name)
        clean_duty = _clean_duty(duty)
        if clean_duty == "检察官":
            return
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", clean_name) or not clean_duty:
            return
        key = (clean_name, clean_duty)
        if key in seen:
            return
        seen.add(key)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=clean_name,
                duty=clean_duty,
                detail_url="",
                evidence=clean_duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=selector_summary,
            )
        )

    for paragraph in region.find_all("p", recursive=False):
        duty_node = paragraph.select_one(":scope > .spanleft")
        name_node = paragraph.select_one(":scope > .spanright")
        if duty_node is not None and name_node is not None:
            continuation_duty = ""
            duty = duty_node.get_text(" ", strip=True)
            for name in _split_names(name_node.get_text(" ", strip=True)):
                append_record(name, duty, "#fontzoom直属段落中的spanleft职务与spanright姓名")
            continue

        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        matched = re.fullmatch(r"(.+?)[：:](.+)", text)
        if matched is not None:
            left, right = matched.groups()
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", left.strip()):
                continuation_duty = ""
                append_record(left, right, "#fontzoom直属段落中的姓名冒号职务")
                continue
            names = _split_names(right)
            for name in names:
                append_record(name, left, "#fontzoom直属段落中的职务冒号姓名名单")
            continuation_duty = _clean_duty(left) if len(names) > 1 else ""
            continue

        names = _split_names(text)
        normalized_source = re.sub(r"[\s、，,；;]+", "", text)
        if continuation_duty and names and "".join(names) == normalized_source:
            for name in names:
                append_record(name, continuation_duty, "#fontzoom多人名单的紧邻纯姓名续行")
        else:
            continuation_duty = ""

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

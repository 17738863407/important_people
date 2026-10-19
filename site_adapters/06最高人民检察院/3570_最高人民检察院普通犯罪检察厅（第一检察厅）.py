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
    "rule_id": "3570",
    "page_type": "配图双栏与跨段职务名单混排页",
    "structure_group": "spp_department_span_pairs_and_continued_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导双栏后另有带排序附注且跨两个段落续行的检察官名单",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def _clean_duty(value: str) -> str:
    """删除字段分隔符和纯排序附注，保留实际职务表述。"""
    duty = _clean_text(value).rstrip("：:")
    duty = re.sub(r"[（(]按(?:姓名|姓氏)笔画(?:为序|排序|排列)?[）)]", "", duty)
    return duty.strip(" ：:")


def _split_names(value: str) -> list[str]:
    """按网页名单分隔符拆分中文姓名。"""
    candidates = re.split(r"[\s、，,；;]+", _clean_text(value))
    return [name for name in candidates if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按 DOM 顺序解析领导双栏和跨段续行的职务名单。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()

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

    continuation_duty = ""
    for paragraph in region.find_all("p", recursive=False):
        spans = paragraph.find_all("span", recursive=False)
        if len(spans) == 2:
            append_record(
                spans[1].get_text(" ", strip=True),
                spans[0].get_text(" ", strip=True),
                "#fontzoom直属段落中的职务span与姓名span",
            )
            continuation_duty = ""
            continue

        text = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:](.+)", text)
        if matched is not None:
            duty, names_text = matched.groups()
            names = _split_names(names_text)
            if names:
                continuation_duty = _clean_duty(duty)
                for name in names:
                    append_record(
                        name,
                        continuation_duty,
                        "#fontzoom职务标题后的首段多人名单",
                    )
                continue

        names = _split_names(text)
        if continuation_duty and names and " ".join(names) == text:
            for name in names:
                append_record(
                    name,
                    continuation_duty,
                    "#fontzoom紧邻职务名单的续行段落",
                )
        elif text:
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

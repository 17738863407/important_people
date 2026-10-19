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
    "rule_id": "3582",
    "page_type": "图片后职务姓名混排页",
    "structure_group": "spp_department_mixed_spans_and_text_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页混用职务姓名双span和职务冒号姓名文本，姓名含全角字间空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理普通排版空白，保留全角空格供姓名边界判断。"""
    text = (value or "").replace("\u2002", "")
    return re.sub(r"[\t\r\n\u00a0 ]+", " ", text).strip()


def _clean_duty(value: str) -> str:
    """删除职务中的字间空格、字段分隔符和纯排序附注。"""
    duty = _clean_text(value).replace("\u3000", "").rstrip("：:")
    duty = re.sub(r"[（(]按(?:姓名|姓氏)笔画(?:为序|排序|排列)?[）)]", "", duty)
    return duty.strip(" ：:")


def _split_names(value: str) -> list[str]:
    """区分全角字间空格与多人名单分隔符。"""
    raw = _clean_text(value)
    candidates = [
        part
        for part in re.split(r"[\u3000\s、，,；;]+", raw)
        if part
    ]
    if 2 <= len(candidates) <= 4 and all(re.fullmatch(r"[\u4e00-\u9fff]", part) for part in candidates):
        candidates = ["".join(candidates)]
    return [name for name in candidates if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文顺序解析双span字段和职务冒号姓名段落。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()

    def append_records(names_text: str, duty_text: str, selector_summary: str) -> None:
        duty = _clean_duty(duty_text)
        if duty == "检察官":
            return
        for name in _split_names(names_text):
            key = (name, duty)
            if not duty or key in seen:
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
                    selector_summary=selector_summary,
                )
            )

    for paragraph in region.find_all("p", recursive=False):
        spans = paragraph.find_all("span", recursive=False)
        if len(spans) == 2:
            append_records(
                spans[1].get_text(" ", strip=True),
                spans[0].get_text(" ", strip=True),
                "#fontzoom直属段落中的两个span职务姓名字段",
            )
            continue

        text = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:](.+)", text)
        if matched is not None:
            duty, names_text = matched.groups()
            append_records(names_text, duty, "#fontzoom直属段落中的职务冒号姓名名单")

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

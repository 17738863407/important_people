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
    "rule_id": "3571",
    "page_type": "配图后职务姓名段落页",
    "structure_group": "spp_department_duty_name_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#fontzoom",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "厅领导与带排序附注的检察官多人名单混排，职务含排版字距",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def _clean_duty(value: str) -> str:
    """删除纯排版字距、字段分隔符和排序附注。"""
    duty = _clean_text(value).rstrip("：:")
    duty = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", duty)
    duty = re.sub(r"[（(]按(?:姓名|姓氏)笔画(?:为序|排序|排列)?[）)]", "", duty)
    return duty.strip(" ：:")


def _split_names(value: str) -> list[str]:
    """按网页名单分隔符拆分中文姓名。"""
    candidates = re.split(r"[\s、，,；;]+", _clean_text(value))
    return [name for name in candidates if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落及段内名单顺序解析人物。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in region.find_all("p", recursive=False):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:](.+)", text)
        if matched is None:
            continue
        duty_text, names_text = matched.groups()
        duty = _clean_duty(duty_text)
        if duty == "检察官":
            continue
        if not duty:
            continue
        for name in _split_names(names_text):
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
                    selector_summary="#fontzoom直属段落中的职务标题与姓名名单",
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

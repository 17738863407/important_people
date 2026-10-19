from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3207",
    "page_type": "多人物详情合并页",
    "structure_group": "xian_emergency_labeled_person_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "xian_emergency_labeled_person_blocks_v2",
    "leader_region_selector": ".u-leader",
    "name_selector": ".p-line .row内姓名标签相邻.txt",
    "duty_selector": ".p-line .row内职务标签相邻.txt",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "人物卡片同时含职责和简历；仅提取明确姓名、职务字段，不补写机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理网页字段中的排版空白，不改变原始语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def field_value(card: object, keyword: str) -> str:
    """从当前人物块的明确标签行读取字段。"""
    for row in card.select(".row"):
        label = row.select_one(":scope > .tnm")
        value = row.select_one(":scope > .txt")
        if not label or not value:
            continue
        normalized_label = re.sub(r"\s+", "", clean_text(label.get_text(" ", strip=True))).rstrip("：:")
        if normalized_label == keyword:
            return clean_text(value.get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块的网页顺序提取姓名及原始职务字段。"""
    from crawler_core.models import PersonRecord

    cards = BeautifulSoup(html or "", "html.parser").select(".u-leader > .p-line")
    if not cards:
        raise RuntimeError("领导信息区域没有人物字段块")
    records: list[object] = []
    seen: set[str] = set()
    for card in cards:
        name = re.sub(r"\s+", "", field_value(card, "姓名"))
        evidence = field_value(card, "职务")
        if re.fullmatch(r"[\u3400-\u9fff\U00020000-\U0002FA1F·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
        if name in seen:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

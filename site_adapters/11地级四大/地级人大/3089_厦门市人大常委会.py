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
    "rule_id": "3089",
    "page_type": "职务分组名单页",
    "structure_group": "xiamen_people_congress_office_groups_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xiamen_people_congress_office_groups_v2",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "页面包含常委会领导及机关多级分组，同一人可能以多个任职重复出现",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    value = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(value.split())


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _clean_duty_label(value: str) -> str:
    """清理职务标题中的姓名或姓氏笔画排序说明。"""
    label = _compact(value)
    label = re.sub(r"[（(]\s*按(?:姓名|姓氏)?笔画[^）)]*[）)]", "", label)
    return label.strip("：:，,。 ")


def _split_names(value: str) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    for raw_name in re.split(r"[、,，]+", value):
        raw_name = _clean_text(raw_name)
        if not raw_name:
            continue
        qualifier = ""
        qualifier_match = re.search(r"（[^）]+）", raw_name)
        if qualifier_match:
            qualifier = _compact(qualifier_match.group(0))
            raw_name = raw_name.replace(qualifier_match.group(0), "")
        name = _compact(raw_name)
        if name == "暂缺" or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        names.append((name, qualifier))
    return names


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按机构标题及其后职务名单的原始DOM顺序生成任职记录。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    for item in region.find_all("div", recursive=False):
        text = _clean_text(item.get_text(" ", strip=True))
        if not text:
            continue
        text = text.replace(" ：", "：").replace("： ", "：").replace(":", "：")
        if "：" not in text:
            continue
        label, name_text = text.split("：", 1)
        label = _clean_duty_label(label)
        if not label or not name_text:
            continue
        for name, _qualifier in _split_names(name_text):
            evidence = label
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

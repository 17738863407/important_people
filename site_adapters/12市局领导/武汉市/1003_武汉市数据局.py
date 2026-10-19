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
    "rule_id": "1003",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_data_bureau_name_duty_items_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_data_bureau_name_duty_items_v2",
    "leader_region_selector": ".ldxx_item",
    "name_selector": ":scope > span:first-of-type",
    "duty_selector": ":scope > span:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "源码注释内含重复职务和“无”占位，仅解析两个可见直属span",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并姓名和职务排版空白。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([，、；：（）])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导条目DOM顺序提取两个直属span中的姓名和原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    items = soup.select(".ldxx_item")

    records: list[object] = []
    seen_names: set[str] = set()
    for item in items:
        fields = item.select(":scope > span")
        if len(fields) != 2:
            raise RuntimeError(f"领导条目可见直属span数量异常：{len(fields)}")
        name = re.sub(r"\s+", "", clean_text(fields[0].get_text(" ", strip=True)))
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导条目姓名或职务异常：{name} {evidence}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if item.select_one("a[href]") is not None:
            raise RuntimeError(f"领导条目出现未审计链接：{name}")
        seen_names.add(name)
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
    if not records:
        raise RuntimeError("领导信息区域没有可见领导条目")
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

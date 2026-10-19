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
    "rule_id": "2617",
    "page_type": "人物列表完整页",
    "structure_group": "xm_commerce_work_division_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_commerce_work_division_paragraphs_v2",
    "leader_region_selector": ".TRS_Editor .TRS_Editor",
    "name_selector": "人物p首个逗号前文本",
    "duty_selector": "同一p首个逗号后、全面或分管前字段",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文后部含AB角姓名噪声；只解析以姓名开头且具有全面或分管边界的独立人物段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理HTML排版空白及标点两侧的版式空格。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([，、])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物分工段落顺序提取姓名和职责边界前的原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到商务局领导分工内层正文")
    pattern = re.compile(
        r"^(?P<name>(?:[\u3400-\u9fff·]\s*){2,10})[，,]\s*"
        r"(?P<duty>.+?)[，,]\s*(?:全面|分管)"
    )
    records: list[object] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", paragraph.get_text(" ", strip=True)).strip()
        match = pattern.match(text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物段落缺少有效姓名或职务")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
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
    if not records:
        raise RuntimeError("领导分工正文中未提取到人物")
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

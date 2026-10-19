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
    "rule_id": "3373",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_housing_zoom_leader_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_housing_zoom_leader_paragraphs_v2",
    "leader_region_selector": "#Zoom",
    "name_selector": "直属段落开头姓名",
    "duty_selector": "直属段落姓名后冒号前完整原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导分工之后存在同名专项工作段及A-B角说明，必须要求姓名后有非空职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并正文排版空白，不改变原始职务语义或标点。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文直属段落顺序解析段首姓名和冒号前职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#Zoom")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域数量异常：{len(regions)}")
    pattern = re.compile(
        r"^(?P<name>(?:[\u3400-\u9fff·]\s*){2,4})\s+"
        r"(?P<evidence>[^：:]{2,80})[：:]"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("evidence")).rstrip("，,；;")
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物段出现未审计链接：{name}")
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
        raise RuntimeError("领导正文没有可验证人物段")
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

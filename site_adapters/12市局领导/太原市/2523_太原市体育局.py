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
    "rule_id": "2523",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_sport_adjacent_name_duty_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_sport_adjacent_name_duty_paragraphs_v2",
    "leader_region_selector": "#zoom",
    "name_selector": "居中姓名短段",
    "duty_selector": "姓名后相邻非空居中职务短段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物按空段、姓名段、职务段重复排列，需忽略空段并保持相邻配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并居中段落中的排版空白。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """忽略空段后按姓名段与紧随职务段成对解析。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#zoom")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    paragraphs = [p for p in regions[0].select(":scope > p") if clean_text(p.get_text(" ", strip=True))]

    records: list[object] = []
    seen_names: set[str] = set()
    index = 0
    while index < len(paragraphs):
        name_node = paragraphs[index]
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            raise RuntimeError(f"姓名段结构异常：{name}")
        if index + 1 >= len(paragraphs):
            raise RuntimeError(f"姓名后缺少职务段：{name}")
        duty_node = paragraphs[index + 1]
        evidence = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"党组(?:书记|成员).+|[一二三四]级调研员", evidence) or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name} / {evidence}")
        if name_node.select_one("a[href]") is not None or duty_node.select_one("a[href]") is not None:
            raise RuntimeError(f"人物姓名或职务段出现未审计链接：{name}")
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
        index += 2
    if not records:
        raise RuntimeError("领导正文没有可验证姓名职务段对")
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

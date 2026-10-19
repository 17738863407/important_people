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
    "rule_id": "2273",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_market_nested_leader_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_market_nested_leader_paragraphs_v2",
    "leader_region_selector": "#Zoom > p > p",
    "name_selector": "人物子段冒号前职务后姓名",
    "duty_selector": "人物子段开头至姓名前完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "无效嵌套p使父段聚合全部人物，必须只解析10个直接人物子段并排除冒号后分管内容",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并人物段落排版空白并清理标点两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按嵌套人物子段DOM顺序提取职务和姓名，排除分管正文。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    paragraphs = soup.select("#Zoom > p > p")
    if not paragraphs:
        raise RuntimeError("领导正文没有人物子段")
    pattern = re.compile(
        r"^(?P<evidence>党组书记、局长|党组成员、副局长|党组成员、二级调研员|"
        r"二级调研员|三级调研员|四级调研员)"
        r"(?P<name>[\u3400-\u9fff·]{2,10})\s*[:：]"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in paragraphs:
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if match is None:
            raise RuntimeError(f"人物子段结构异常：{text}")
        name = match.group("name")
        evidence = match.group("evidence")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物子段出现未审计链接：{name}")
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

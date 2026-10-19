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
    "rule_id": "2466", "page_type": "人物列表完整页", "structure_group": "sjz_ethnic_colon_paragraph_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_ethnic_colon_paragraph_v2",
    "leader_region_selector": "#conN > p", "name_selector": "人物p冒号前原文",
    "duty_selector": "人物p冒号后至首个句号", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "首个句号后的主持、分管或协助文本属于职责；页面另含非领导数据iframe",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在每个人物段落内按冒号与首个句号边界提取姓名和职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    paragraphs = regions[0].find_all("p", recursive=False)
    if not paragraphs:
        raise RuntimeError("领导正文没有直接人物段落")

    records: list[object] = []
    seen_names: set[str] = set()
    pattern = re.compile(r"^(?P<name>[^：:]+)[：:](?P<duty>[^。]+)。(?P<responsibility>.+)$")
    for paragraph in paragraphs:
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            raise RuntimeError(f"人物段落结构异常：{text}")
        name = re.sub(r"\s+", "", clean_text(match.group("name")))
        evidence = clean_text(match.group("duty"))
        responsibility = clean_text(match.group("responsibility"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if not responsibility.startswith(("主持", "分管", "协助")):
            raise RuntimeError(f"人物职责字段边界异常：{name} {responsibility}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物段落出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
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

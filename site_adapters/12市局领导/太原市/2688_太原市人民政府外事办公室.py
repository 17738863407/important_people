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
    "rule_id": "2688",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_foreign_affairs_nested_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_foreign_affairs_nested_paragraphs_v2",
    "leader_region_selector": "#Zoom > p > p",
    "name_selector": "人物子段冒号前姓名",
    "duty_selector": "人物子段冒号后市外事办起始完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "无效嵌套p使父段聚合全体人物，必须只解析非空直接人物子段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并人物子段中的排版空白并清理冒号两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*[:：]\s*", "：", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按直接人物子段DOM顺序解析姓名和完整原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    paragraphs = soup.select("#Zoom > p > p")
    if not paragraphs:
        raise RuntimeError("领导正文没有人物子段")
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,10})：(?P<evidence>市外事办.+)$")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in paragraphs:
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        match = pattern.fullmatch(text)
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
    if not records:
        raise RuntimeError("领导正文没有可验证人物子段")
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

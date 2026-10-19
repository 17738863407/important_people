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
    "rule_id": "1899",
    "page_type": "人物列表完整页",
    "structure_group": "ngtc_leader_alternating_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".detai_left_txt",
    "name_selector": "p span[style*='font-size: 20px']",
    "duty_selector": "姓名p后的下一个非空兄弟p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名含Unicode排版空格，姓名职务按交替段落排列",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理网页排版空白。"""
    value = re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([，、])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """以姓名段为锚点读取紧随其后的非空职务段。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    for paragraph in soup.select(".detai_left_txt > p"):
        name_node = paragraph.select_one("span[style*='font-size: 20px']")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(paragraph.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        duty = ""
        sibling = paragraph.find_next_sibling("p")
        while sibling is not None and not duty:
            duty = _clean_text(sibling.get_text(" ", strip=True))
            sibling = sibling.find_next_sibling("p")
        if not duty:
            continue
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
                selector_summary="detai_left_txt内20px姓名段及下一非空职务段",
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

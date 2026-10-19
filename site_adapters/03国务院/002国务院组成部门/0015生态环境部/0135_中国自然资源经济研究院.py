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
    "rule_id": "0135",
    "page_type": "人物列表完整页",
    "structure_group": "canre_leader_colon_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div#vsb_content",
    "name_selector": "p中中文冒号前文本",
    "duty_selector": "p中中文冒号后文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务中含全角空格和排版空白",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理段落排版空白。"""
    value = re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff，、：])\s+(?=[\u4e00-\u9fff])", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按单位领导正文中的“姓名：职务”段落顺序提取。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    for paragraph in soup.select("div#vsb_content p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text:
            continue
        name, duty = (_clean_text(value) for value in text.split("：", 1))
        name = re.sub(r"\s+", "", name)
        if not name or not duty:
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
                selector_summary="vsb_content内姓名冒号职务段落",
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

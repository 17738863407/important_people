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
    "rule_id": "2648",
    "page_type": "职务分组名单页",
    "structure_group": "duty_colon_name_responsibility_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiGeologicalDutyNameParagraphParser_v1",
    "leader_region_selector": ".news_text p",
    "name_selector": "冒号后首个姓名",
    "duty_selector": "冒号前文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "人物段落在姓名后继续包含主持/分管职责，依据只保留冒号前职务",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析“职务：姓名”，排除姓名后的职责。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".news_text p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text:
            continue
        duty, rest = text.split("：", 1)
        duty = _clean_text(duty)
        match = re.match(r"\s*([\u4e00-\u9fff·]{2,8})(?:\s|$)", rest)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": ".news_text p；职务=冒号前文本；姓名=冒号后首个姓名",
                "order": str(len(records) + 1),
            }
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

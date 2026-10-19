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
    "rule_id": "3040",
    "page_type": "人物列表完整页",
    "structure_group": "xbmu_current_leader_duty_name_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "xbmu_current_leader_duty_name_paragraphs_v1",
    "leader_region_selector": "#vsb_content",
    "name_selector": "#vsb_content p",
    "duty_selector": "#vsb_content p",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["#vsb_content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "正文首尾含空段落，仅接受严格职务冒号姓名结构",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序解析严格的“职务：姓名”结构。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#vsb_content")
    if region is None:
        return []

    records: list[object] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in region.select("p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(.{2,40}?)\s*[：:]\s*([\u3400-\u9fff\s]{2,10})", evidence)
        if match is None:
            continue
        duty = _clean_text(match.group(1))
        name = _clean_name(match.group(2))
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
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
                selector_summary="#vsb_content p；严格职务冒号姓名结构",
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

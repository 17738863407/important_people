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
    "rule_id": "1103",
    "page_type": "人物列表完整页",
    "structure_group": "jazx_name_duty_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "jazx_name_duty_paragraphs_v2",
    "leader_region_selector": "td.content",
    "name_selector": "td.content p.MsoNormal",
    "duty_selector": "td.content p.MsoNormal",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文段落为姓名职务合并字段；页面没有独立人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文人物段落顺序解析“姓名：职务”字段。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for paragraph in region.select("p.MsoNormal"):
        label = _clean_text(paragraph.get_text("", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u3400-\u9fff·]{2,20})[：:](?P<duty>.+)",
            label,
        )
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty").strip("，,、 ")
        if not duty or name in seen:
            continue
        seen.add(name)
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

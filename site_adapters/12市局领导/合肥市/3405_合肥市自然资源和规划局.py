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
    "rule_id": "3405",
    "page_type": "人物列表完整页",
    "structure_group": "hefei_natural_resources_labeled_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "hefei_natural_resources_labeled_paragraphs_v1",
    "leader_region_selector": ".j-fontContent.ptlmcontent",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "仅接受唯一领导正文中相邻的姓名、职务标签段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写字段语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序配对明确标注的姓名和职务字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文命中数量异常：{len(regions)}")

    lines = [
        _clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in regions[0].select("p")
    ]
    lines = [line for line in lines if line]
    records: list[object] = []
    seen_names: set[str] = set()
    index = 0
    while index < len(lines):
        name_match = re.fullmatch(r"姓名[：:]\s*(?P<name>[一-鿿·]{2,8})", lines[index])
        if not name_match:
            index += 1
            continue
        if index + 1 >= len(lines):
            raise RuntimeError("末个人物姓名后缺少职务段")
        duty_match = re.fullmatch(r"职务[：:]\s*(?P<duty>.+)", lines[index + 1])
        if not duty_match:
            raise RuntimeError(f"姓名 {name_match.group('name')} 后未紧邻职务段")

        name = name_match.group("name")
        duty = _clean_text(duty_match.group("duty"))
        if name in seen_names or not duty or len(duty) > 120:
            raise RuntimeError(f"姓名重复或职务异常：{name}")
        seen_names.add(name)
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
        index += 2

    if not records:
        raise RuntimeError("领导正文未解析到姓名职务记录")
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

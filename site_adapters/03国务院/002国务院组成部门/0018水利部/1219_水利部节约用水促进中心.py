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
    "rule_id": "1219",
    "page_type": "职务分组名单页",
    "structure_group": "jszx_duty_group_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "jszx_duty_group_paragraphs_v2",
    "leader_region_selector": ".detailContent .view",
    "name_selector": ".detailContent .view p",
    "duty_selector": ".detailContent .view p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "存在职务标签但名单为空的分组；不得从整页导航补取姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序解析职务分组及顿号名单。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        label = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>[\u3400-\u9fff]{2,20})[：:](?P<names>.*)",
            label,
        )
        if match is None:
            continue
        duty = match.group("duty")
        names_text = match.group("names")
        for raw_name in re.split(r"[、，,]", names_text):
            name = re.sub(r"\s+", "", raw_name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen:
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

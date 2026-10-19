from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2516",
    "page_type": "人物列表完整页",
    "structure_group": "shaanxi_survey_leader_link_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "a[href*='/Home/LingDaoZhiChuang/']",
    "name_selector": "p开头中文姓名",
    "duty_selector": "p中姓名后原始文本",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "list_links"},
    "risk_flag": "",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导卡片DOM顺序提取姓名、职务和独立详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for link in soup.select("a[href*='/Home/LingDaoZhiChuang/']"):
        paragraph = link.select_one(":scope > p")
        if paragraph is None:
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff]{2,4})\s+(?P<duty>.+)", text)
        if match is None:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
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
                detail_url=urljoin(final_url, link.get("href", "")),
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="领导之窗链接卡片姓名职务",
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

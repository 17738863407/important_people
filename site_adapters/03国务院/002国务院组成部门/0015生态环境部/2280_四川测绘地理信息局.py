from __future__ import annotations

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
    "rule_id": "2280",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_survey_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": "section ol.fl_jse > li",
    "name_selector": "a p:nth-of-type(2)",
    "duty_selector": "a p:nth-of-type(1)",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "list_links"},
    "risk_flag": "普通HTTP当前返回508，online需浏览器兜底",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return " ".join(value.replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按局领导卡片DOM顺序提取职务、姓名和独立详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for card in soup.select("section ol.fl_jse > li"):
        link = card.select_one(":scope > a[href]")
        if link is None:
            continue
        fields = [_clean_text(node.get_text(" ", strip=True)) for node in link.select(":scope > p")]
        fields = [field for field in fields if field]
        if len(fields) < 2:
            continue
        duty, name = fields[0], fields[1]
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
                selector_summary="fl_jse局领导卡片职务姓名",
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

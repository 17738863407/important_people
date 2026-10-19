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
    "rule_id": "3092",
    "page_type": "职务分组名单页",
    "structure_group": "xining_people_congress_grouped_leaders_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xining_people_congress_grouped_leaders_v3",
    "leader_region_selector": "div.leader_cloumn",
    "name_selector": "a[title][href]",
    "duty_selector": "h3.leader_tit",
    "detail_link_selector": "a[title][href]",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "职务取自当前人物分组的明确标题；人物链接仅作为详情页链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按主任之窗的职务分组及页面顺序提取人物。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if not regions:
        return []

    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for region in regions:
        heading = region.select_one("h3.leader_tit")
        evidence = re.sub(r"\s+", "", heading.get_text(" ", strip=True)) if heading else ""
        if not evidence:
            continue
        for link in region.select("a[title][href]"):
            name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", link.get("title") or link.get_text(" ", strip=True))
            if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            seen.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=evidence,
                    detail_url=urljoin(entry_url, link["href"]),
                    evidence=evidence,
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

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
    "rule_id": "0214",
    "page_type": "人物导航详情页",
    "structure_group": "chengdu_government_leader_navigation_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "custom_parse_page",
    "parser": "chengdu_government_leader_navigation_v2",
    "leader_region_selector": "main",
    "name_selector": 'a[href*="leader_list"], a[href*="/zfxx/ld_"]',
    "duty_selector": 'a[href*="leader_list"], a[href*="/zfxx/ld_"]',
    "detail_link_selector": 'a[href*="leader_list"], a[href*="/zfxx/ld_"]',
    "detail_strategy": {
        "required": False,
        "mode": "navigation_links",
        "max_detail_links": 50,
    },
    "risk_flag": "普通HTTP触发412，使用Chrome CDP渲染；仅解析main内姓名加职务导航",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市政府领导导航DOM顺序解析姓名、原始职务和人物链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,19})\s+(?P<duty>.+)",
            text,
        )
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = match.group("duty").strip()
        if name in seen or not duty or duty == "更多":
            continue
        seen.add(name)
        candidate_url = urljoin(entry_url, link["href"])
        detail_url = "" if candidate_url.rstrip("/") == entry_url.rstrip("/") else candidate_url
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
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

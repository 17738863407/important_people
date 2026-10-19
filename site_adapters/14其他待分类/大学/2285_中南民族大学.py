from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2285",
    "page_type": "职务分组名单页",
    "structure_group": "scuec_current_leader_grouped_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "scuec_current_leader_grouped_list_v1",
    "leader_region_selector": ".xrld",
    "name_selector": ".dwlist > .flex a[href]",
    "duty_selector": ".dwlist > .flex > em",
    "detail_link_selector": ".dwlist > .flex a[href]",
    "content_scope": {
        "include_selectors": [".xrld"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": ".dwlist > .flex a[href]",
        "max_detail_links": 50,
    },
    "risk_flag": "党委与行政分组存在同名人物，需按首次出现顺序聚合",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _clean_duty(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """遍历党委和行政职务组，并聚合同一人物的多项职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xrld")
    if region is None:
        return []

    entry_url = page_rule["url"]
    people: dict[str, dict[str, object]] = {}
    for item in region.select(".dwlist > .flex"):
        duty_node = item.select_one(":scope > em")
        if duty_node is None:
            continue
        duty = _clean_duty(duty_node.get_text(" ", strip=True))
        if not duty:
            continue

        for anchor in item.select("a[href]"):
            name = _clean_name(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            href = anchor.get("href", "").strip()
            candidate = urljoin(final_url, href)
            detail_url = ""
            if (
                href
                and not href.startswith(("#", "javascript:", "mailto:"))
                and _normalize_url(candidate) != _normalize_url(entry_url)
            ):
                detail_url = candidate

            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            duties = person["duties"]
            if duty not in duties:
                duties.append(duty)
            if not person["detail_url"] and detail_url:
                person["detail_url"] = detail_url

    records: list[object] = []
    for name, person in people.items():
        duty = "；".join(person["duties"])
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=entry_url,
                name=name,
                duty=duty,
                detail_url=person["detail_url"],
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".xrld .dwlist > .flex: em + a[href]",
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

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
    "rule_id": "1837",
    "page_type": "职务分组名单页",
    "structure_group": "ningbo_renda_duty_colon_name_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ningbo_renda_duty_colon_name_links_v1",
    "leader_region_selector": ".lead_group01",
    "name_selector": "a[href] .name",
    "duty_selector": "a[href] .name",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "include_selectors": [".lead_group01"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "a[href] .name",
        "max_detail_links": 20,
    },
    "risk_flag": "领导区另含无姓名的组织机构图片链接，必须要求.name节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value)).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导链接顺序拆分明确的“职务：姓名”节点。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".lead_group01")
    if region is None:
        return []

    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for anchor in region.select("a[href]"):
        name_node = anchor.select_one(".name")
        if name_node is None:
            continue
        evidence = _clean_text(name_node.get_text(" ", strip=True))
        if "：" not in evidence:
            continue
        duty, raw_name = [_clean_text(part) for part in evidence.split("：", 1)]
        name = _clean_name(raw_name)
        if not duty or name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            continue
        duty = re.sub(r"\s+", "", duty)
        href = anchor.get("href", "").strip()
        detail_url = urljoin(final_url, href)
        if (
            not href
            or href.startswith(("#", "javascript:", "mailto:"))
            or _normalize_url(detail_url) == _normalize_url(entry_url)
        ):
            detail_url = ""
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=entry_url,
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".lead_group01 a[href] .name按全角冒号拆分",
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

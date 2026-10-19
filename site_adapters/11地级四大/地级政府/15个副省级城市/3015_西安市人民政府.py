from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3015",
    "page_type": "人物目录详情页",
    "structure_group": "xian_government_sidebar_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xian_government_sidebar_profiles_v2",
    "leader_region_selector": "ul.ld-mayor",
    "name_selector": "li > span > a[href]",
    "duty_selector": ".ld-bg .positions",
    "detail_link_selector": "li > span > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_profile_fields",
        "detail_content_selector": ".ld-bg",
        "max_detail_links": 20,
    },
    "risk_flag": "侧栏仅区分市长和市政府领导，具体职务必须从对应人物页positions字段读取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _clean_duty(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _canonical_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导侧栏顺序逐页读取姓名与positions职务字段。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select("li > span > a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, link["href"])))

    records: list[object] = []
    for source_order, (expected_name, detail_url) in enumerate(candidates):
        fetch_result = fetch_html_with_strategy(
            detail_url,
            strategy="online",
            timeout=60,
            request_attempt_offset=source_order,
        )
        detail_soup = BeautifulSoup(fetch_result.html, "html.parser")
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        name_node = profile.select_one(".name") if profile else None
        duty_node = profile.select_one(".positions") if profile else None
        profile_name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_duty(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if profile_name != expected_name or not evidence:
            raise RuntimeError(
                f"目录与人物页字段无法核对：{expected_name} -> {profile_name or '空'}"
            )
        verified_detail_url = (
            ""
            if _canonical_url(fetch_result.final_url) == _canonical_url(page_rule["url"])
            else fetch_result.final_url
        )
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=profile_name,
                duty=evidence,
                detail_url=verified_detail_url,
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

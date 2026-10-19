from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2658",
    "page_type": "人物目录详情页",
    "structure_group": "shenzhen_government_rendered_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "shenzhen_government_rendered_profiles_v2",
    "leader_region_selector": ".zx_ldzc_left",
    "name_selector": "ul > li:not(.tit) > a[href]",
    "duty_selector": ".zx_ldzc_right #jl",
    "detail_link_selector": "ul > li:not(.tit) > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "playwright_current_sentence",
        "detail_content_selector": ".zx_ldzc_right #jl",
        "max_detail_links": 20,
    },
    "risk_flag": "站点TLS导致requests失败，已核验无头Playwright可稳定取得领导侧栏和人物简介DOM",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _canonical_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按渲染侧栏顺序，用无头Playwright逐页提取完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select("ul > li:not(.tit) > a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        seen.add(name)
        candidates.append((name, link["href"]))

    records: list[object] = []
    for expected_name, detail_url in candidates:
        fetch_result = fetch_html_with_strategy(
            detail_url,
            strategy="playwright",
            timeout=60,
        )
        detail_soup = BeautifulSoup(fetch_result.html, "html.parser")
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        profile_text = _clean_text(profile.get_text(" ", strip=True)) if profile else ""
        evidence_match = re.search(r"现任[^。]*。", profile_text)
        if expected_name not in profile_text or evidence_match is None:
            raise RuntimeError(f"人物详情现任信息无法核对：{expected_name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).rstrip("。")
        verified_detail_url = (
            ""
            if _canonical_url(fetch_result.final_url) == _canonical_url(page_rule["url"])
            else fetch_result.final_url
        )
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=expected_name,
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

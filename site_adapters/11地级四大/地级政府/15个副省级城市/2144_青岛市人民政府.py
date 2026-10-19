from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2144",
    "page_type": "职务分组详情页",
    "structure_group": "qingdao_government_grouped_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "qingdao_government_grouped_profiles_v2",
    "leader_region_selector": "#dw_dq .ldleft",
    "name_selector": "li > p > a[href]",
    "duty_selector": "#dw_dq .wright .ldjlc",
    "detail_link_selector": "li > p > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": "#dw_dq .wright",
        "max_detail_links": 30,
    },
    "risk_flag": "页面同时列出副秘书长，详情人物区另含分工；只在标题为简介的ldjlc中提取现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _canonical_url(value: str) -> str:
    parts = urlsplit(urldefrag(value)[0])
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按分组名单顺序抓取每个当前人物简介中的完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select("li > p > a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        seen.add(name)
        candidates.append((name, urldefrag(link["href"])[0]))

    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    for expected_name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        heading = profile.select_one(".szzp p") if profile else None
        heading_text = _clean_text(heading.get_text(" ", strip=True)) if heading else ""
        intro = next(
            (
                block
                for block in profile.select(".ldjlc")
                if block.select_one("div span")
                and _clean_text(block.select_one("div span").get_text(" ", strip=True))
                == "简介"
            ),
            None,
        ) if profile else None
        intro_text = _clean_text(intro.get_text(" ", strip=True)) if intro else ""
        evidence_match = re.search(r"现任[^。]*。", intro_text)
        if expected_name not in heading_text or evidence_match is None:
            raise RuntimeError(f"人物页简介无法核对：{expected_name}")
        evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
        verified_detail_url = (
            ""
            if _canonical_url(response.url) == _canonical_url(page_rule["url"])
            else response.url
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

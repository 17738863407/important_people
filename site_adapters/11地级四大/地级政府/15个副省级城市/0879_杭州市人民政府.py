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
    "rule_id": "0879",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_government_profile_navigation_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "hangzhou_government_profile_navigation_v2",
    "leader_region_selector": ".sidenav .col_list",
    "name_selector": "li > a[href]",
    "duty_selector": ".cont.bt-right .profession .profession_name",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_profile_field",
        "detail_content_selector": ".cont.bt-right > .profession",
        "max_detail_links": 20,
    },
    "risk_flag": "详情页在现任职务后同时展示领导分工和活动列表，必须限定在profession字段内",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _canonical_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按政府领导导航顺序抓取详情页中独立的“现任职务”结构字段。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select(page_rule["name_selector"]):
        label = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u3400-\u9fff·\s]{2,20})\s+(市长|常务副市长|副市长)", label)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    for expected_name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        profession = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        if profession is None:
            raise RuntimeError(f"人物详情缺少现任职务结构字段：{expected_name}")

        name_node = profession.select_one(".profession_name .name")
        profile_name = (
            re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
            if name_node is not None
            else ""
        )
        if profile_name != expected_name:
            raise RuntimeError(
                f"人物导航与详情姓名不一致：{expected_name} -> {profile_name or '空'}"
            )

        field = profession.select_one(".profession_name")
        field_text = _clean_text(field.get_text(" ", strip=True)) if field else ""
        evidence = _clean_text(field_text[len(expected_name) :]) if field_text.startswith(expected_name) else ""
        if not evidence:
            raise RuntimeError(f"人物详情缺少可验证的现任职务内容：{expected_name}")

        verified_detail_url = (
            ""
            if _canonical_url(response.url) == _canonical_url(page_rule["url"])
            else response.url
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

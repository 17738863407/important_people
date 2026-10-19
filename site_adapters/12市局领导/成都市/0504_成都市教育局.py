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
    "rule_id": "0504",
    "page_type": "人物表格页",
    "structure_group": "chengdu_education_leader_table_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "custom_parse_page",
    "parser": "chengdu_education_leader_table_profiles_v1",
    "leader_region_selector": "table[align=center][width='90%']",
    "name_selector": "tbody > tr > td[align=left] > a[href]",
    "duty_selector": "div.content-info",
    "detail_link_selector": "tbody > tr > td[align=left] > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_profile_current_sentence",
        "detail_content_selector": "div.content-info",
        "detail_name_selector": "div.title > div:first-of-type",
        "max_detail_links": 20,
    },
    "risk_flag": "入口页及人物页普通HTTP请求返回412，需使用Chrome CDP读取当前DOM",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写原始语义。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _clean_name(value: str) -> str:
    """清理姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _canonical_url(value: str) -> str:
    """生成用于入口页与详情页语义核对的规范URL。"""
    parts = urlsplit(value)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def _extract_current_sentence(profile: object) -> str:
    """仅在当前人物简介区域提取完整“现任……”原文句。"""
    profile_text = _clean_text(profile.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", profile_text)
    return re.sub(r"^现任\s*", "", match.group(0)).rstrip("。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导表格顺序动态读取人物链接，并核对详情简介中的现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导表格命中数量异常：{len(regions)}")

    entry_url = final_url or page_rule["url"]
    entry_parts = urlsplit(entry_url)
    candidates: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for link in regions[0].select(page_rule["name_selector"]):
        name = _clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(entry_url, str(link.get("href") or ""))
        detail_parts = urlsplit(detail_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if detail_parts.netloc.lower() != entry_parts.netloc.lower():
            continue
        if not re.fullmatch(
            r"/cdedu/c112923/\d{4}-\d{2}/\d{2}/content_[a-f0-9]+\.shtml",
            detail_parts.path,
        ):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        candidates.append((name, detail_url))

    max_detail_links = int(page_rule["detail_strategy"]["max_detail_links"])
    if not candidates or len(candidates) > max_detail_links:
        raise RuntimeError(f"人物详情链接数量异常：{len(candidates)}")

    records: list[object] = []
    for expected_name, detail_url in candidates:
        fetch_result = fetch_html_with_strategy(
            detail_url,
            strategy="chrome",
            timeout=60,
        )
        detail_soup = BeautifulSoup(fetch_result.html, "html.parser")
        name_node = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_name_selector"]
        )
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        profile_name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _extract_current_sentence(profile) if profile else ""
        if profile_name != expected_name or not evidence:
            raise RuntimeError(
                f"目录与人物页现任字段无法核对：{expected_name} -> {profile_name or '空'}"
            )

        verified_detail_url = fetch_result.final_url
        if _canonical_url(verified_detail_url) == _canonical_url(page_rule["url"]):
            verified_detail_url = ""
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

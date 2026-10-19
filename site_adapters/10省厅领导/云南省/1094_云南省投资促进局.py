from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1094",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_investment_gov_directory_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_yunnan_investment_directory_details_v2",
    "leader_region_selector": ".lzy-gov-com-list a[title][href]",
    "name_selector": "目录title末尾与详情.article-body首个非空p开头的交集",
    "duty_selector": "详情.article-body首个非空p中姓名后的文本",
    "detail_link_selector": ".lzy-gov-com-list a[title][href]",
    "content_scope": {
        "start_anchor": "领导信息首项",
        "end_anchor": "领导信息末项",
        "include_selectors": [".lzy-gov-com-list a[title][href]", ".article-body p"],
        "exclude_selectors": ["AB角分工文章", "负责分管段", "导航与页脚"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".lzy-gov-com-list a[title][href]",
        "detail_name_selector": ".article-body首个非空p开头",
        "detail_duty_selector": ".article-body首个非空p姓名后文本",
        "detail_content_selector": ".article-body",
        "max_detail_links": 50,
    },
    "risk_flag": "目录人物标题为机构+职务+姓名且无分隔；通过标题末尾与详情首段开头交叉匹配姓名，排除同列表AB角非人物文章",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".lzy-gov-com-list a[title][href]",
            "name_selector": "目录title末尾与详情首段开头动态交叉匹配",
            "duty_selector": ".article-body首个非空p姓名后文本",
            "detail_link_selector": ".lzy-gov-com-list当前目录href",
            "content_scope": {
                "start_anchor": "领导信息首项",
                "end_anchor": "领导信息末项",
                "include_selectors": [".lzy-gov-com-list a[title][href]", ".article-body p"],
                "exclude_selectors": ["AB角分工文章", "负责分管段", "导航与页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML目录与详情首段可交叉确定姓名和职务，无需固定机构或职务前缀"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "article-list" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _detail_url(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, href)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if "/zwgk/fdzdgknr/jgxx/ldxx/" not in parsed.path or not parsed.path.endswith(".html"):
        return ""
    return resolved


def _extract_detail(list_title: str, detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    profile = ""
    for paragraph in soup.select(".article-body p"):
        profile = _compact_text(paragraph.get_text(" ", strip=True))
        if profile:
            break
    title = _compact_text(list_title)
    if not profile or not title:
        return "", ""
    candidates: list[str] = []
    for length in range(2, min(30, len(profile) - 1) + 1):
        candidate = profile[:length]
        if title.endswith(candidate) and re.fullmatch(r"[\u4e00-\u9fff·.]{2,30}", candidate):
            candidates.append(candidate)
    if not candidates:
        return "", ""
    name = max(candidates, key=len)
    duty = profile[len(name) :]
    return (name, duty) if duty else ("", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".lzy-gov-com-list a[title][href]"):
        if _is_hidden(link):
            continue
        list_title = _clean_text(str(link.get("title", "")))
        detail_url = _detail_url(base_url, str(link.get("href", "")))
        if not list_title or not detail_url:
            continue
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            name, duty = _extract_detail(list_title, response.text)
        except requests.RequestException:
            name, duty = "", ""
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_yunnan_investment_directory_details_v2",
                "selector_summary": "目录title末尾×详情首段开头姓名；首段余文为职务",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

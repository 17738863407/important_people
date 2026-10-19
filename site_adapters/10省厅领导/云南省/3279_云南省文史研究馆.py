from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3279",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_history_research_leader_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_yunnan_history_research_leader_directory_details_v2",
    "leader_region_selector": "#about_app .about-item（标题为领导简介）",
    "name_selector": ".list-item[pc-url]",
    "duty_selector": "人物详情简历末个年月任职句",
    "detail_link_selector": ".list-item[pc-url]的pc-url属性",
    "content_scope": {
        "start_anchor": "领导简介",
        "end_anchor": "领导简介分组末项",
        "include_selectors": ["#about_app .about-item .list-item[pc-url]"],
        "exclude_selectors": ["机构简介", "内设机构", "直属事业单位", "分工段落"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_parse_page",
        "detail_collector_type": "raw_http",
        "detail_link_selector": ".list-item[pc-url]的pc-url属性",
        "detail_name_selector": "人物详情正文首个简历段",
        "detail_duty_selector": "人物详情简历末个年月任职句",
        "detail_content_selector": "人物详情正文p",
        "max_detail_links": 20,
    },
    "risk_flag": "入口同页含机构简介、内设机构和直属事业单位；按领导简介标题限定分组，并仅在对应详情简历中提取末个年月任职句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#about_app .about-item（标题为领导简介）",
            "name_selector": ".list-item[pc-url]",
            "duty_selector": "人物详情简历末个年月任职句",
            "detail_link_selector": ".list-item[pc-url]的pc-url属性",
            "content_scope": {
                "start_anchor": "领导简介",
                "end_anchor": "领导简介分组末项",
                "include_selectors": ["#about_app .about-item .list-item[pc-url]"],
                "exclude_selectors": ["机构简介", "内设机构", "直属事业单位", "分工段落"],
            },
        },
        "api": {"enabled": False, "reason": "入口和人物详情静态HTML直接提供姓名、任职原句及独立人物链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "about-item" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _find_leader_region(soup: BeautifulSoup) -> Tag | None:
    for title in soup.select("#about_app .about-item .title span"):
        if _clean_text(title.get_text(" ", strip=True)) != "领导简介":
            continue
        region = title.find_parent(class_="about-item")
        if isinstance(region, Tag) and not _is_hidden(region):
            return region
    return None


def _extract_detail_duty(html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    appointment_pattern = re.compile(
        r"(?P<evidence>(?:19|20)\d{2}年\d{1,2}月任(?P<duty>[^。；;]+)[。；;]?)"
    )
    matches: list[re.Match[str]] = []
    for paragraph in soup.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if name not in text and not text.startswith("历任"):
            continue
        matches.extend(appointment_pattern.finditer(text))
    if not matches:
        return "", ""
    match = matches[-1]
    duty = _clean_text(match.group("duty")).strip(" ：:，,。.；;")
    evidence = _clean_text(match.group("evidence"))
    if evidence and evidence[-1] not in "。；;":
        evidence += "。"
    return duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    region = _find_leader_region(soup)
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in region.select(".list-item[pc-url]"):
        if _is_hidden(item):
            continue
        name = re.sub(r"\s+", "", _clean_text(item.get_text(" ", strip=True)))
        detail_path = str(item.get("pc-url") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not detail_path or name in seen:
            continue

        detail_url = urljoin(final_url, detail_path)
        detail_result = fetch_by_raw_requests(detail_url)
        duty, evidence = _extract_detail_duty(detail_result.html, name)
        if not duty or not evidence:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": evidence,
                "parser": "custom_yunnan_history_research_leader_directory_details_v2",
                "selector_summary": "领导简介.list-item[pc-url]；对应详情p末个年月任职句",
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

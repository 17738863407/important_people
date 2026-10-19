from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1291",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_education_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_education_list_detail_v2",
    "leader_region_selector": ".zfxxgk-right",
    "name_selector": ".zfxxgk-right a[href]",
    "duty_selector": "详情页个人简历区域内完整现任句",
    "detail_link_selector": ".zfxxgk-right a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_link_selector": ".zfxxgk-right a[href]",
        "max_detail_links": 30,
    },
    "risk_flag": "列表页只提供姓名；必须按DOM顺序读取一对一详情，并将完整现任句作为原文依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfxxgk-right",
            "detail_link_selector": "a[href]",
            "detail_content_selector": ".TRS_UEDITOR, .TRS_Editor, .content",
        },
        "api": {"enabled": False, "reason": "领导列表及人物详情均由静态HTML提供"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_people(html: str, final_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    people: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(".zfxxgk-right a[href]"):
        name = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", anchor.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen or not detail_url:
            continue
        seen.add(name)
        people.append((name, detail_url))
    return people


def parse_detail(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_UEDITOR, .TRS_Editor, .content")
    if region is None:
        return ""
    text = normalize_layout(region.get_text(" ", strip=True))
    if expected_name not in text:
        return ""
    match = re.search(r"现任[^。]*。", text)
    return match.group(0).removeprefix("现任").removesuffix("。") if match is not None else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    people = discover_people(html, final_url)
    if not people:
        return []
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    for name, detail_url in people:
        detail = fetch_html_with_strategy(detail_url, strategy="requests")
        evidence = parse_detail(detail.html, name)
        if not evidence:
            raise RuntimeError(f"人物详情页缺少可回指的姓名或完整现任句：{detail_url}")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".zfxxgk-right人物链接按DOM顺序；逐详情个人简历区域提取完整现任句",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

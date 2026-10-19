from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2677",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_municipal_garden_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_municipal_garden_list_detail_v2",
    "leader_region_selector": ".zfxxgk-right .nav1Cont ul.has_line",
    "name_selector": "人物链接文本",
    "duty_selector": "详情简介完整现任句或首个姓名职务短段",
    "detail_link_selector": ".zfxxgk-right .nav1Cont ul.has_line li a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 30},
    "risk_flag": "历史脚本依赖详情快照；少数详情没有现任句，须在同一详情首个姓名职务短段内回退，不得读取后续分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".zfxxgk-right .nav1Cont ul.has_line", "detail_link_selector": "li a[href]", "detail_content_selector": ".trs_editor_view, .TRS_UEDITOR, .TRS_Editor"}, "api": {"enabled": False, "reason": "人物列表与一对一详情均由静态HTML提供"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_people(html: str, final_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    people: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(".zfxxgk-right .nav1Cont ul.has_line li a[href]"):
        name = normalize_layout(anchor.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        seen.add(name)
        people.append((name, detail_url))
    return people


def parse_detail(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".trs_editor_view, .TRS_UEDITOR, .TRS_Editor")
    if region is None:
        return ""
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        if expected_name not in text:
            continue
        current = re.search(r"现任[^。]*。", text)
        if current is not None:
            return re.sub(r"^现任\s*", "", current.group(0)).strip(" ，,。；;：: ")
        if text.startswith(expected_name) and len(text) <= 120 and re.search(r"(?:纪检监察组组长|局长|党组|调研员)", text):
            return re.sub(rf"^{re.escape(expected_name)}\s*", "", text).strip(" ，,。；;：: ")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    people = discover_people(html, final_url)
    if not people:
        return []
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    for name, detail_url in people:
        evidence = parse_detail(fetch_html_with_strategy(detail_url, strategy="requests").html, name)
        if not evidence:
            raise RuntimeError(f"人物详情页缺少可回指的现任句或首个姓名职务段：{detail_url}")
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "桌面端.has_line人物链接按DOM顺序；逐详情优先完整现任句，否则首个姓名职务短段"})
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

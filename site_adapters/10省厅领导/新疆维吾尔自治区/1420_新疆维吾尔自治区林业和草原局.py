from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1420",
    "page_type": "人物目录详情页",
    "structure_group": "xinjiang_forestry_directory_detail_current_intro",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_forestry_directory_detail_current_intro_v1",
    "leader_region_selector": ".ldypos",
    "name_selector": "a[title][href*='/lcj/ldxx/']",
    "duty_selector": "详情当前人物.content_p简介中的现任片段",
    "detail_link_selector": "a[title][href*='/lcj/ldxx/']",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": ["a[title][href*='/lcj/ldxx/']", "详情strong现任简介"], "exclude_selectors": ["扫描分享至微信", "友情链接", "页脚"]},
    "detail_strategy": {"required": True, "mode": "directory_details", "detail_collector_type": "static_http", "detail_link_selector": "a[title][href*='/lcj/ldxx/']", "detail_name_selector": "详情标题", "detail_duty_selector": ".content_p简介现任片段", "detail_content_selector": ".content_p", "max_detail_links": 50},
    "risk_flag": "详情页现任简介跨多个span且标签闭合不一致；只在当前人物.content_p内合并文本，禁止全页搜索至分享/友情链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".ldypos", "name_selector": "a[title][href*='/lcj/ldxx/']", "duty_selector": "详情.content_p现任片段", "detail_link_selector": "a[title][href*='/lcj/ldxx/']", "content_scope": {"start_anchor": "现任", "end_anchor": "当前.content_p结束", "include_selectors": [".content_p"], "exclude_selectors": ["分享", "友情链接", "页脚"]}},
        "api": {"enabled": False, "reason": "当前静态HTML目录和人物简介可直接提供姓名、现任职务和详情链接"},
    },
}


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_current_intro(html: str, expected_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".content_p")
    if scope is None:
        return "", ""
    text = _clean_text(scope.get_text(" ", strip=True))
    if expected_name not in text:
        return "", ""
    match = re.search(r"现任(?P<duty>.+)$", text)
    if match is not None:
        duty = _clean_text(match.group("duty")).strip(" ：:，,。")
        if duty:
            return duty, duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[title][href*='/lcj/ldxx/']"):
        name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            continue
        detail_html, detail_url = _fetch_detail(urljoin(base_url, str(link.get("href", ""))))
        duty, evidence = _extract_current_intro(detail_html, name)
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": evidence, "parser": "custom_xinjiang_forestry_directory_detail_current_intro_v1", "selector_summary": "目录title姓名链接；详情strong当前人物现任片段"})
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

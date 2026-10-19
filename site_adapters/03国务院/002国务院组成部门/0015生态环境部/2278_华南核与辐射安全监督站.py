from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2278",
    "page_type": "人物目录详情页",
    "structure_group": "scro_leader_list_to_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_scro_leader_list_to_detail_v2",
    "leader_region_selector": ".main a[href]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": ".main a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".main"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".main a[href]",
        "detail_parser": "page_inline_scro_current_duty_sentence_v2",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": ".TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": "目录姓名含版面空格；只在当前人物详情正文内提取完整现任句，禁止使用本地详情文件",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail",
    "locator": {
        "css": {
            "leader_region_selector": ".main a[href]",
            "detail_link_selector": ".main a[href]",
            "detail_content_selector": ".TRS_Editor",
        },
        "api": {"enabled": False, "reason": "当前目录和人物详情页静态HTML提供姓名、现任句和链接"},
        "migration": {
            "source": "legacy_offline_detail_dependency_and_business_source_removed",
            "verified_status": "verified_current_raw_http_details",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()
    normalized = re.sub(r"\s*([、，。；])\s*", r"\1", normalized)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", normalized)


def _fetch_detail(session: requests.Session, url: str) -> str:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    errors: list[str] = []
    for _ in range(6):
        try:
            response = session.get(url, timeout=25, verify=False)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            errors.append(str(exc))
    raise RuntimeError(f"人物详情页抓取失败：{url}；{' | '.join(errors)}")


def _extract_current_duty(html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".TRS_Editor")
    if content is None:
        return "", ""
    text = _clean_text(content.get_text(" ", strip=True))
    match = re.search(rf"{re.escape(name)}，(现任([^。]+)。)", text)
    if match is None:
        return "", ""
    duty = _clean_text(match.group(2))
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录DOM顺序在线抓取每个人物详情页中的完整现任句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
            "Referer": final_url,
        }
    )
    records: list[PersonRecord] = []
    seen_urls: set[str] = set()
    for link in soup.select(".main a[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+([\u4e00-\u9fff·\s]{2,20})", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        detail_url = urljoin(final_url, link.get("href", ""))
        if detail_url in seen_urls:
            continue
        detail_html = _fetch_detail(session, detail_url)
        duty, evidence = _extract_current_duty(detail_html, name)
        if not duty:
            continue
        seen_urls.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="目录日期姓名链接 + 详情.TRS_Editor现任句",
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

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.nx.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "collector": "static_http",
        "parser": "page_ningxia_education_leader_link_title_v1",
        "leader_region_selector": ".scroll_main .zfxxgk_zd2 a[href]",
        "name_selector": ".scroll_main .zfxxgk_zd2 a title/text prefix",
        "duty_selector": ".scroll_main .zfxxgk_zd2 a title/text suffix",
        "detail_link_selector": ".scroll_main .zfxxgk_zd2 a[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": None,
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
        },
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".scroll_main .zfxxgk_zd2 a[href]",
                "name_selector": "link title/text prefix",
                "duty_selector": "link title/text suffix",
                "detail_link_selector": ".scroll_main .zfxxgk_zd2 a[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "委厅领导列表页链接文本已直接包含姓名和职务"},
        },
    }


def split_name_duty(raw_text: str) -> tuple[str, str] | None:
    text = normalize_space(raw_text)
    match = re.match(r"([\u4e00-\u9fff·]\s*[\u4e00-\u9fff·](?:\s*[\u4e00-\u9fff·]){0,3})\s+(.+)", text)
    if not match:
        return None

    name = clean_name(match.group(1))
    duty = normalize_space(match.group(2))
    if not is_name(name) or not duty or len(duty) > 90:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for link in soup.select(".scroll_main .zfxxgk_zd2 a[href]"):
        raw_text = link.get("title") or link.get_text(" ", strip=True)
        result = split_name_duty(raw_text)
        if not result:
            continue
        name, duty = result
        if name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(base_url, link.get("href", "").strip())
        detail = urlparse(detail_url)
        source = urlparse(str(page_rule.get("url", "")) or final_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not detail.path.lower().endswith((".html", ".htm"))
        ):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.scroll_main .zfxxgk_zd2 a；split=title prefix/suffix",
            }
        )

    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.models import PersonRecord
    from crawler_core.naming import build_output_name

    page_rule = apply_business_source(build_page_rule(rule_id))
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        str(page_rule["url"]),
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    raw_rows = parse_page(response.text, response.url, page_rule)
    records = [
        PersonRecord(
            organization=str(page_rule["organization"]),
            url=str(page_rule["url"]),
            name=str(row.get("name", "")),
            duty=str(row.get("duty", "")),
            detail_url=str(row.get("detail_url", "")),
            evidence=str(row.get("evidence", "")),
            confidence=str(page_rule.get("confidence", "high")),
            parser=str(row.get("parser", "")),
            selector_summary=str(row.get("selector_summary", "")),
            script_sequence=str(page_rule["rule_id"]),
        )
        for row in raw_rows
    ]
    if not records:
        raise RuntimeError("在线直连获取成功，但原定位解析结果为空")
    output_name = build_output_name(page_rule["rule_id"], page_rule["organization"])
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, records)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1341"
    main(rule_id_value)
